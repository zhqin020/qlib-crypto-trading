
import logging
from typing import Dict
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os
import pandas as pd
from datetime import datetime

from serving.schema import SimulationAccount, Position, Order, OrderSide, OrderStatus
from serving.exchange import ExchangeConnector

logger = logging.getLogger("OMS")

class LocalOrderManager:
    """
    Simulated Order Management System (OMS).
    Executes trades against a PostgreSQL-backed local paper portfolio.
    """
    
    def __init__(self, db_url: str, account_name: str = "OKX_Paper", exchange_connector: ExchangeConnector = None):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.account_name = account_name
        self.config = {
            "slippage": 0.001,  # 0.1% simulated slippage
            "fee_rate": 0.0005, # 0.05% taker fee
        }
        self.connector = exchange_connector

    def _get_account(self, session):
        return session.query(SimulationAccount).filter_by(name=self.account_name).first()

    def sync_market_prices(self):
        """
        Fetch latest prices for all held positions to update Equity and Unrealized PnL.
        """
        if not self.connector:
            logger.warning("No Exchange Connector provided. Skipping price sync.")
            return

        session = self.Session()
        account = self._get_account(session)
        if not account:
            session.close()
            return
            
        positions = account.positions
        total_pnl = 0.0
        
        for pos in positions:
            # Fetch real-time price
            try:
                # We fetch a single 1m candle or ticker
                ticker = self.connector.exchange.fetch_ticker(pos.symbol)
                current_price = ticker['last']
                
                # Update Position Stats
                pos.current_price = current_price
                
                # PnL = (Current - Entry) * Amount
                # If shorting is supported (negative amount), math holds:
                # Long: (110 - 100) * 1 = +10
                # Short: (90 - 100) * -1 = +10
                pos.unrealized_pnl = (current_price - pos.entry_price) * pos.amount
                
                total_pnl += pos.unrealized_pnl
                
            except Exception as e:
                logger.error(f"Failed to sync price for {pos.symbol}: {e}")
        
        
        # Recalculate Equity
        # Equity = Cash + Unrealized PnL of Positions + Margin Used?
        # In a generic "Balance + Positions" model:
        # Balance is "Total Cash + Realized PnL".
        # Equity = Balance + Sum(Unrealized PnL)
        
        # NOTE: In Net Position system (Future):
        # Position Value isn't directly added to Equity unless it's Spot.
        # For Futures: Equity = Balance + Unrealized PnL.
        
        total_unrealized_pnl = sum([p.unrealized_pnl for p in positions])
        account.equity = account.balance + total_unrealized_pnl
        
        session.commit()
        session.close()
        logger.info(f"Market Sync Complete. Balance: {account.balance:.2f}, Equity: {account.equity:.2f}")

    def execute_rebalance(self, target_weights: Dict[str, float], current_prices: Dict[str, float]):
        """
        Rebalance portfolio to match target weights.
        
        :param target_weights: Dict {symbol: weight}. Sum should be <= 1.0 (long) or leverage aware.
        :param current_prices: Dict {symbol: price}. Latest market prices.
        """
        session = self.Session()
        account = self._get_account(session)
        
        if not account:
            logger.error(f"Account {self.account_name} not found!")
            session.close()
            return

        # 1. Total Equity to Allocate
        total_equity = account.equity
        logger.info(f"Rebalancing Portfolio. Equity: ${total_equity:.2f}")

        # 2. Get Current Positions map
        current_positions = {p.symbol: p for p in account.positions}
        
        # 3. Calculate Target Amounts
        target_amounts = {}
        for symbol, weight in target_weights.items():
            price = current_prices.get(symbol)
            if not price:
                logger.error(f"No price found for {symbol}. Skipping.")
                continue
            
            # Value = Equity * Weight
            # Weight can be > 1.0 (Leverage) or < 0.0 (Short)
            
            target_value = total_equity * weight
            
            # Amount = Value / Price
            # If Weight is -0.5 (Short), Value is negative, Amount is negative.
            # This aligns with our Net Position model (Amount < 0 for Short).
            
            amount = target_value / price
            target_amounts[symbol] = amount

        # 4. Generate Orders (Diff)
        # Handle Exits (Held but not in target OR target is different)
        all_symbols = set(current_positions.keys()) | set(target_amounts.keys())
        
        for symbol in all_symbols:
            curr_pos = current_positions.get(symbol)
            curr_amt = curr_pos.amount if curr_pos else 0.0
            
            target_amt = target_amounts.get(symbol, 0.0)
            
            diff_amt = target_amt - curr_amt
            
            # Threshold to avoid dust trades (e.g. < $5 value)
            price = current_prices.get(symbol, 0)
            if price == 0 and curr_pos:
                price = curr_pos.current_price
            
            if abs(diff_amt * price) < 5.0:
                continue
                
            side = OrderSide.BUY if diff_amt > 0 else OrderSide.SELL
            abs_amt = abs(diff_amt)
            
            # Execute Trade Simulation
            self._fill_order(session, account, symbol, side, abs_amt, price)
            
        session.commit()
        session.close()

    def _fill_order(self, session, account, symbol, side, amount, market_price):
        """
        Simulate order fill with slippage and fees.
        """
        # Slippage: Buy pays more, Sell gets less
        slippage_factor = 1 + self.config['slippage'] if side == OrderSide.BUY else 1 - self.config['slippage']
        fill_price = market_price * slippage_factor
        
        # Fee (on Notional)
        notional_value = amount * fill_price
        fee = notional_value * self.config['fee_rate']
        
        # Update Balance (Cash)
        # For Futures/Margin:
        # Cash only changes on Fee + Realized PnL.
        # We are simplifying:
        # If we "Buy Asset", we spend cash? No, that's Spot.
        # If we simulate FUTURES/SWAPS:
        # Opening a position doesn't cost Cash (except margin, which is locked).
        # We only pay Fee. 
        # Cash changes when PnL is realized.
        
        # LOGIC CHANGE: Future-Style Simulation
        # Balance = Cash Balance (Wallet)
        # Entry/Exit updates PnL.
        
        # 1. Deduct Fee
        account.balance -= fee
        
        # 2. Check for Realized PnL (Closing/Reducing position)
        position = session.query(Position).filter_by(account_id=account.id, symbol=symbol).first()
        realized_pnl = 0.0
        
        # If no position exists, we are opening. No PnL.
        if not position:
            position = Position(account_id=account.id, symbol=symbol, amount=0.0, entry_price=0.0)
            session.add(position)
            
        old_amt = position.amount
        signed_change = amount if side == OrderSide.BUY else -amount
        new_amt = old_amt + signed_change
        
        # Determine if we are reducing/closing
        is_closing = False
        if old_amt > 0 and signed_change < 0: # Long reducing
            is_closing = True
        elif old_amt < 0 and signed_change > 0: # Short reducing
            is_closing = True
            
        if is_closing:
            # Calculate Closed Portion
            # If old 10, new 5. Closed 5.
            # If old 10, new -5 (Flip). Closed 10.
            
            start_sign = 1 if old_amt > 0 else -1
            
            # Amount closed is min(|change|, |old_amt|)
            abs_change = abs(signed_change)
            abs_old = abs(old_amt)
            
            closed_qty = min(abs_change, abs_old)
            
            # Pnl = (Exit Price - Entry Price) * qty * sign
            # e.g. Long (sign 1). Exit 110. Entry 100. (110-100)*1 = 10.
            # Short (sign -1). Exit 90. Entry 100. (90-100)*-1 = 10.
            
            realized_pnl = (fill_price - position.entry_price) * closed_qty * start_sign
            
            account.balance += realized_pnl
            logger.info(f"Realized PnL: {realized_pnl:.2f}")

        # Update Position Stats (Entry Price)
        # Logic: 
        # 1. Increasing Position: Weighted Average Entry.
        # 2. Decreasing Position: Entry Price stays same.
        # 3. Flips: Remainder is new open.
        
        if (old_amt > 0 and signed_change > 0) or (old_amt < 0 and signed_change < 0):
            # Increasing exposure
            # e.g. Long 10 @ 100. Buy 10 @ 110.
            # New Amt 20. Cost 1000 + 1100 = 2100. Avg 105.
            total_cost = (abs(old_amt) * position.entry_price) + (amount * fill_price)
            new_entry = total_cost / abs(new_amt)
            position.entry_price = new_entry
            
        elif (old_amt == 0):
             position.entry_price = fill_price
             
        elif (old_amt > 0 and new_amt < 0) or (old_amt < 0 and new_amt > 0):
            # FLIP
            # Closed all old. Opened new remainder at fill_price.
            position.entry_price = fill_price # The new entry price for the flipped portion
        
        # If purely closing (without flipping), entry price doesn't change. 
        
        position.current_price = market_price 
        # Recalculate Unrealized PnL based on new amount
        position.amount = new_amt
        position.unrealized_pnl = (market_price - position.entry_price) * new_amt
        
        # Create Order Record
        order = Order(
            account_id=account.id, 
            symbol=symbol,
            side=side,
            type="market",
            amount=amount,
            price=fill_price,
            fee=fee,
            status=OrderStatus.FILLED
        )
        session.add(order)
        
        logger.info(f"EXECUTED {side.value.upper()} {symbol}: {amount:.4f} @ {fill_price:.2f} (Fee: {fee:.4f})")
        
        # Cleanup dust / closed positions
        if abs(position.amount * market_price) < 1.0:
            session.delete(position)

