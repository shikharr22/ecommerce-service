import os
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL=os.getenv("DATABASE_URL") or "postgres://dev:devpass@localhost:5432/ecommerce_dev"
