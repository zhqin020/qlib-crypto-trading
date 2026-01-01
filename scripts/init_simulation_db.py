
import logging
from sqlalchemy import create_engine
from serving.schema import Base, SimulationAccount
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Use existing DB URL or default
DB_URL = os.getenv("DATABASE_URL", "postgresql://crypto_user:crypto@localhost:5432/qlib_crypto")

logger = logging.getLogger("InitDB")
logging.basicConfig(level=logging.INFO)

def init_db():
    engine = create_engine(DB_URL)
    logger.info(f"Connecting to database...")
    
    # Create Tables
    Base.metadata.create_all(engine)
    logger.info("Tables created successfully.")
    
    # Initialize Default Simulated Account if not exists
    Session = sessionmaker(bind=engine)
    session = Session()
    
    account_name = "OKX_Paper"
    existing = session.query(SimulationAccount).filter_by(name=account_name).first()
    
    if not existing:
        logger.info(f"Creating default simulation account: {account_name}")
        acc = SimulationAccount(name=account_name, balance=10000.0, equity=10000.0)
        session.add(acc)
        session.commit()
    else:
        logger.info(f"Account {account_name} already exists. Balance: {existing.balance}")
        
    session.close()

if __name__ == "__main__":
    init_db()
