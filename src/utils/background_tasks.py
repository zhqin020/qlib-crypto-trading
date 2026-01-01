"""Background tasks for periodic maintenance"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from data_pipeline.data_refresh import DataRefreshConfig, run_data_refresh

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """Manages periodic background tasks"""

    def __init__(self):
        self._tasks = []
        self._running = False
        self._data_refresh_config = DataRefreshConfig.from_env()

    async def start(self):
        """Start all background tasks"""
        if self._running:
            logger.warning("Background tasks already running")
            return

        self._running = True
        logger.info("Starting background tasks")

        # Load state on startup
        from monitoring.process_monitor import monitor
        try:
            if os.getenv("PYTEST_CURRENT_TEST"):
                logger.debug("Skipping state load during tests")
                restored = 0
            else:
                restored = await monitor.load_state()
                logger.info(f"Loaded {restored} processes from state file")
                await monitor.start_redis_listener()
                await monitor.get_all_processes()
        except Exception as e:
            logger.error(f"Failed to load state on startup: {e}", exc_info=True)

        if self._data_refresh_config.active:
            if os.getenv("PYTEST_CURRENT_TEST"):
                logger.debug("Skipping data refresh loop during tests")
            else:
                task = asyncio.create_task(self._data_refresh_loop())
                self._tasks.append(task)
        elif self._data_refresh_config.enabled:
            logger.warning(
                "Automated data refresh is enabled but no symbols are configured;"
                " set DATA_REFRESH_SYMBOLS to activate the refresh loop."
            )

        # Start cleanup task
        self._tasks.append(asyncio.create_task(self._cleanup_old_processes()))

        # Start auto-save task
        self._tasks.append(asyncio.create_task(self._auto_save_state()))

        # Start Trading Loop if enabled
        trading_cfg = await self._get_trading_config()
        enabled = os.getenv("TRADING_LOOP_ENABLED", str(trading_cfg.get("live_loop_enabled", "false"))).lower() == "true"
        
        if enabled:
            if os.getenv("PYTEST_CURRENT_TEST"):
                logger.debug("Skipping trading loop during tests")
            else:
                interval = int(os.getenv("TRADING_LOOP_INTERVAL", trading_cfg.get("live_loop_interval", 3600)))
                self._tasks.append(asyncio.create_task(self._trading_loop(interval)))
                logger.info(f"Automated trading loop started with interval {interval}s")
        else:
            logger.info("Automated trading loop is disabled")

    async def _get_trading_config(self):
        """Helper to load trading config from file"""
        try:
            from pathlib import Path
            import json
            config_path = Path("config/trading_params.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f).get("trading", {})
        except Exception as e:
            logger.error(f"Failed to load trading config: {e}")
        return {}

    async def _trading_loop(self, interval: int):
        """Background loop for real-time trading execution"""
        from serving.live_loop import LiveTradingLoop
        import time
        
        # Initialize loop
        try:
            logger.info("Initializing LiveTradingLoop...")
            loop = LiveTradingLoop()
            logger.info("LiveTradingLoop initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize LiveTradingLoop: {e}", exc_info=True)
            return

        while self._running:
            start_time = time.time()
            try:
                # Monitored process for UI tracking
                from monitoring.process_monitor import monitor
                process_id = f"trading_cycle_{int(time.time())}"
                
                await monitor.start_process(process_id, "trading")
                await monitor.update_progress(process_id, 10, "Starting cycle")
                
                await loop.run_once()
                
                await monitor.complete_process(process_id, {"status": "success"})
                
            except Exception as e:
                logger.error(f"Trading cycle failed: {e}", exc_info=True)
                # Fail in monitor if it was started
                try:
                    await monitor.fail_process(process_id, str(e))
                except:
                    pass
            
            elapsed = time.time() - start_time
            sleep_time = max(10, interval - elapsed) # Min 10s safety
            
            logger.info(f"Trading cycle complete. Next run in {sleep_time:.2f}s")
            
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break

    async def stop(self):
        """Stop all background tasks"""
        self._running = False
        logger.info("Stopping background tasks")

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()
        try:
            from monitoring.process_monitor import monitor
            await monitor.stop_redis_listener()
        except Exception as e:
            logger.error(f"Failed to stop Redis listener: {e}", exc_info=True)

    async def _cleanup_old_processes(self):
        """Periodically clean up old completed processes"""
        from monitoring.process_monitor import monitor

        while self._running:
            try:
                # Clean up processes older than 24 hours
                removed = await monitor.cleanup_old_processes(max_age_hours=24)
                if removed > 0:
                    logger.info(f"Cleaned up {removed} old processes")

                # Wait 1 hour before next cleanup
                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _auto_save_state(self):
        """Periodically save process state to disk every 5 minutes"""
        from monitoring.process_monitor import monitor

        while self._running:
            try:
                # Wait 5 minutes between saves
                await asyncio.sleep(300)

                # Save state
                saved_count = await monitor.save_state()
                logger.debug(f"Auto-saved state for {saved_count} processes")

            except asyncio.CancelledError:
                # Save state one final time before exiting
                try:
                    saved_count = await monitor.save_state()
                    logger.info(f"Final state save: {saved_count} processes")
                except Exception as e:
                    logger.error(f"Failed to save state on shutdown: {e}", exc_info=True)
                break
            except Exception as e:
                logger.error(f"Error in auto-save task: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _data_refresh_loop(self):
        """Background loop that keeps prediction datasets fresh."""
        config = self._data_refresh_config
        if not config.active:
            return

        logger.info(
            "Automated data refresh enabled for dataset '%s' (interval=%s, frequency=%d minutes)",
            config.dataset,
            config.interval,
            config.frequency_minutes,
        )

        delay = 0
        backoff = min(900, config.frequency_seconds)

        while self._running and config.active:
            if delay:
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    raise

            if not self._running or not config.active:
                break

            try:
                started = datetime.utcnow()
                result = await run_data_refresh(config)
                duration = (datetime.utcnow() - started).total_seconds()

                status = result.get("status")
                if status == "ok":
                    logger.info(
                        "Market data refresh completed in %.1fs (%s → %s)",
                        duration,
                        result.get("start_date"),
                        result.get("end_date"),
                    )
                    delay = config.frequency_seconds
                    backoff = min(backoff, delay)
                elif status == "disabled":
                    logger.info("Data refresh disabled dynamically; stopping loop")
                    break
                else:
                    logger.error("Market data refresh failed: %s", result.get("error"))
                    delay = backoff
                    backoff = min(backoff * 2, config.frequency_seconds)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Unexpected data refresh error: %s", exc, exc_info=True)
                delay = backoff
                backoff = min(backoff * 2, config.frequency_seconds)

        logger.info("Data refresh loop stopped")


# Global instance
background_manager = BackgroundTaskManager()
