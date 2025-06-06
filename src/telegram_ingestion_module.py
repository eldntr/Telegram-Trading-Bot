# telegram_ingestion_module.py
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import PeerUser, PeerChat, PeerChannel, InputPeerChannel
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError, UserIdInvalidError, ChatIdInvalidError as TelethonChatIdInvalidError

import config # Menggunakan config.py yang sudah kita buat
from signal_parser import TelegramSignalParser
from signal_models import BaseMessage # Untuk type hinting

class TelegramSignalIngestionModule:
    def __init__(self, api_id: int, api_hash: str, session_name: str, phone_number: str, target_chat_id: int):
        self.client = TelegramClient(session_name, api_id, api_hash, system_version="4.16.30-vxCUSTOM")
        self.phone_number = phone_number
        self.target_chat_id = target_chat_id
        self.parser = TelegramSignalParser()
        self._event_queue = asyncio.Queue()
        self.target_entity = None
        self._message_handler_ref = None # Initialize attribute

        @self.client.on(events.NewMessage()) # Listen on all, then filter in handler
        async def _message_handler_wrapper(event):
            # Filter for the specific chat ID here
            # This is more robust if self.target_entity is resolved later
            if self.target_entity:
                if event.chat_id == self.target_entity.id:
                    print(f"--- Pesan Baru Diterima (ID: {event.message.id}) dari Chat ID: {event.chat_id} ---")
                    parsed_signal = self.parser.parse_message(event.message)
                    await self._event_queue.put(parsed_signal)
            # Fallback if entity not yet resolved, or if using raw ID (less ideal for channels)
            elif event.chat_id == self.target_chat_id:
                 print(f"--- Pesan Baru Diterima (ID: {event.message.id}) dari Chat ID: {event.chat_id} (using raw ID) ---")
                 parsed_signal = self.parser.parse_message(event.message)
                 await self._event_queue.put(parsed_signal)

        self._message_handler_ref = _message_handler_wrapper


    async def _resolve_target_entity(self):
        """Helper function to resolve the target entity."""
        if self.target_entity:
            return self.target_entity

        try:
            print(f"Resolving entity for Chat ID: {self.target_chat_id}...")
            # Heuristic: If it's a negative ID not starting with -100,
            # assume it's -<bare_channel_id> for a channel/megagroup.
            if self.target_chat_id < 0 and not str(self.target_chat_id).startswith("-100"):
                bare_channel_id = abs(self.target_chat_id)
                print(f"Attempting to resolve as PeerChannel with channel_id: {bare_channel_id}")
                entity = await self.client.get_entity(PeerChannel(channel_id=bare_channel_id))
            else:
                # Handles user IDs, marked channel IDs (-100...), positive bare channel/chat IDs (less common alone), usernames
                entity = await self.client.get_entity(self.target_chat_id)
            
            self.target_entity = entity
            print(f"Entity resolved: {getattr(entity, 'title', entity.id)}")
            return entity
        except (ValueError, TelethonChatIdInvalidError, UserIdInvalidError) as e:
            print(f"Could not resolve chat ID {self.target_chat_id} using get_entity. Error: {e}")
            if "GetChatsRequest" in str(e) or "ChatIdInvalidError" in str(type(e).__name__):
                 print("This error often means the ID is incorrect, the bot/user isn't in the chat/channel, or it's a channel ID that needs to be wrapped in PeerChannel(abs(ID)).")
            return None
        except Exception as e: # Catch other potential errors
            print(f"An unexpected error occurred while trying to get entity for {self.target_chat_id}: {e}")
            return None

    async def _process_event_queue(self):
        while True:
            parsed_signal: BaseMessage = await self._event_queue.get()
            try:
                print(f"PARSED SIGNAL ({parsed_signal.message_type}):")
                print(parsed_signal)
                print("-" * 30)
            except Exception as e:
                print(f"Error processing parsed signal: {e}")
            finally:
                self._event_queue.task_done()

    async def start_listening(self):
        print("Menghubungkan ke Telegram...")
        await self.client.connect()
        if not await self.client.is_user_authorized():
            print("User belum terotorisasi. Mengirim kode...")
            await self.client.send_code_request(self.phone_number)
            try:
                await self.client.sign_in(self.phone_number, input('Masukkan kode OTP: '))
            except Exception as e:
                print(f"Gagal sign in: {e}")
                await self.client.disconnect()
                return
        
        print(f"Terhubung sebagai: {(await self.client.get_me()).first_name}")

        resolved_entity = await self._resolve_target_entity()
        if not resolved_entity:
            print(f"Failed to resolve target entity {self.target_chat_id}. Exiting listener.")
            await self.client.disconnect()
            return

        # Update event handler to specifically listen on the resolved entity if desired
        # self.client.remove_event_handler(self._message_handler_ref)
        # self.client.add_event_handler(self._message_handler_ref, events.NewMessage(chats=[resolved_entity]))
        # For now, the wrapper filters internally.

        print(f"Mendengarkan pesan dari: {getattr(resolved_entity, 'title', resolved_entity.id)}...")
        asyncio.create_task(self._process_event_queue())
        await self.client.run_until_disconnected()

    async def fetch_historical_messages(self, limit: int = 10):
        print(f"Mengambil {limit} pesan terakhir dari Chat ID: {self.target_chat_id}...")
        
        if not self.client.is_connected():
            await self.client.connect()
        
        if not await self.client.is_user_authorized():
            print("User belum terotorisasi. Silakan jalankan start_listening() dulu untuk login atau pastikan session file is valid.")
            # Consider disconnecting if not authorized and not attempting sign-in
            # await self.client.disconnect() 
            return

        resolved_entity = await self._resolve_target_entity()
        if not resolved_entity:
            print(f"Failed to resolve target entity {self.target_chat_id} for historical fetch. Cannot proceed.")
            # await self.client.disconnect() # Optional: disconnect if entity resolution fails
            return []


        messages_data = []
        try:
            print(f"Fetching messages from entity: {getattr(resolved_entity, 'title', resolved_entity.id)}")
            async for message in self.client.iter_messages(resolved_entity, limit=limit):
                print(f"\n--- Memproses Pesan Historis (ID: {message.id}) ---")
                parsed_signal = self.parser.parse_message(message)
                messages_data.append(parsed_signal)
                print(f"PARSED HISTORICAL ({parsed_signal.message_type}):")
                print(parsed_signal)
        except (ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError) as e:
            print(f"Cannot access chat {getattr(resolved_entity, 'title', self.target_chat_id)}. Permissions issue or private channel: {e}")
        except Exception as e:
            print(f"Error fetching historical messages from {getattr(resolved_entity, 'title', self.target_chat_id)}: {e}")
        
        print(f"\n--- Selesai mengambil pesan historis ---")
        return messages_data

async def main():
    if not isinstance(config.API_ID, int) or not config.API_HASH or not config.PHONE_NUMBER or not isinstance(config.TARGET_CHAT_ID, int):
         print("Harap konfigurasikan API_ID (int), API_HASH (str), PHONE_NUMBER (str), dan TARGET_CHAT_ID (int) di config.py atau .env file sebelum menjalankan.")
         return

    module = TelegramSignalIngestionModule(
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_name=config.SESSION_NAME,
        phone_number=config.PHONE_NUMBER,
        target_chat_id=config.TARGET_CHAT_ID
    )

    # Opsi 1: Ambil pesan historis untuk testing parser
    await module.fetch_historical_messages(limit=20)
    if module.client.is_connected(): # Ensure disconnection if only fetching history
        await module.client.disconnect()
        print("Disconnected after fetching historical messages.")

    # Opsi 2: Mulai mendengarkan pesan baru secara real-time
    # print("\nTo start listening for new messages, uncomment the section below in main()")
    # try:
    #     print("Starting to listen for new messages...")
    #     await module.start_listening()
    # except KeyboardInterrupt:
    #     print("Proses dihentikan oleh pengguna.")
    # finally:
    #     if module.client and module.client.is_connected():
    #         await module.client.disconnect()
    #         print("Koneksi Telegram ditutup.")

if __name__ == "__main__":
    asyncio.run(main())