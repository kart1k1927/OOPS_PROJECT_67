import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load the environment variables from the .env file
load_dotenv()

# Get the URL and Key from the environment
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")

# Create the Supabase client
supabase: Client = create_client(url, key)
