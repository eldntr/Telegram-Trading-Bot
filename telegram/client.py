# telegram/client.py
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError

class TelegramClientWrapper:
    """Wrapper untuk klien Telethon untuk menangani koneksi dan pengambilan pesan."""

    def __init__(self, session_name: str, api_id: int, api_hash: str, phone_number: str):
        self.client = TelegramClient(session_name, api_id, api_hash, system_version="4.16.30-vxCUSTOM")
        self.phone_number = phone_number

    async def connect(self):
        """Menghubungkan ke Telegram dan menangani otorisasi."""
        await self.client.connect()
        if not await self.client.is_user_authorized():
            print("Pengguna belum terotorisasi. Mengirim kode...")
            await self.client.send_code_request(self.phone_number)
            try:
                await self.client.sign_in(self.phone_number, input('Masukkan kode OTP: '))
            except Exception as e:
                print(f"Gagal sign in: {e}")
                await self.client.disconnect()
                raise

    async def disconnect(self):
        """Memutuskan koneksi klien."""
        await self.client.disconnect()

    async def fetch_historical_messages(self, chat_id: int, limit: int = 10):
        """Mengambil pesan historis dari chat tertentu."""
        try:
            entity = await self.client.get_entity(PeerChannel(abs(chat_id))) if chat_id < 0 else await self.client.get_entity(chat_id)
            messages = await self.client.get_messages(entity, limit=limit)
            return messages
        except (ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError) as e:
            print(f"Tidak dapat mengakses chat {chat_id}. Masalah izin atau channel pribadi: {e}")
        except Exception as e:
            print(f"Error saat mengambil pesan historis dari {chat_id}: {e}")
        return []