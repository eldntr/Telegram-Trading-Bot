import asyncio
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError

class TelegramClientWrapper:
    """A wrapper for the Telethon client to handle connection and message fetching."""

    def __init__(self, session_name: str, api_id: int, api_hash: str, phone_number: str):
        self.client = TelegramClient(session_name, api_id, api_hash, system_version="4.16.30-vxCUSTOM")
        self.phone_number = phone_number

    async def connect(self):
        """Connects to Telegram and handles authorization."""
        await self.client.connect()
        if not await self.client.is_user_authorized():
            print("User not authorized. Sending code...")
            await self.client.send_code_request(self.phone_number)
            try:
                await self.client.sign_in(self.phone_number, input('Enter OTP code: '))
            except Exception as e:
                print(f"Failed to sign in: {e}")
                await self.client.disconnect()
                raise

    async def disconnect(self):
        """Disconnects the client."""
        await self.client.disconnect()

    async def fetch_historical_messages(self, chat_id: int, limit: int = 10):
        """Fetches historical messages from a specific chat."""
        try:
            entity = await self.client.get_entity(PeerChannel(abs(chat_id))) if chat_id < 0 else await self.client.get_entity(chat_id)
            messages = await self.client.get_messages(entity, limit=limit)
            return messages
        except (ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError) as e:
            print(f"Cannot access chat {chat_id}. Permission issue or private channel: {e}")
        except Exception as e:
            print(f"Error fetching historical messages from {chat_id}: {e}")
        return []