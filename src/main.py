import asyncio
from . import config
from .telegram_client import TelegramClientWrapper
from .signal_parser import TelegramSignalParser
from .json_writer import JsonWriter

async def main():
    """Main function to run the message fetching and parsing process."""
    if not all([config.API_ID, config.API_HASH, config.PHONE_NUMBER, config.TARGET_CHAT_ID]):
        print("Please configure API_ID, API_HASH, PHONE_NUMBER, and TARGET_CHAT_ID in your .env file.")
        return

    client_wrapper = TelegramClientWrapper(
        session_name=config.SESSION_NAME,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        phone_number=config.PHONE_NUMBER
    )
    
    parser = TelegramSignalParser()
    json_writer = JsonWriter("parsed_messages.json")
    
    try:
        await client_wrapper.connect()
        print(f"Connected as {(await client_wrapper.client.get_me()).first_name}")
        
        historical_messages = await client_wrapper.fetch_historical_messages(
            chat_id=config.TARGET_CHAT_ID,
            limit=100
        )
        
        parsed_data = [parser.parse_message(msg).to_dict() for msg in historical_messages]
        
        if parsed_data:
            json_writer.write(parsed_data)
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if client_wrapper.client.is_connected():
            await client_wrapper.disconnect()
            print("Disconnected from Telegram.")

if __name__ == "__main__":
    asyncio.run(main())