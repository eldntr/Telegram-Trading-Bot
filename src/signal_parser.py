# signal_parser.py
import re
from datetime import datetime
from typing import Optional, Union, List, Dict, Any, Tuple
from signal_models import (
    SignalUpdate, NewSignal, MarketAlert, UnstructuredMessage,
    TargetInfo, StopLossInfo, BaseMessage
)

class TelegramSignalParser:

    def _extract_sender_and_timestamp(self, message_obj: Any) -> Dict[str, Any]:
        """Helper untuk mengekstrak info umum dari objek pesan Telethon."""
        timestamp = message_obj.date if hasattr(message_obj, 'date') else datetime.now()
        sender_id = None
        if hasattr(message_obj, 'sender_id'):
            sender_id = message_obj.sender_id
        elif hasattr(message_obj, 'from_id') and hasattr(message_obj.from_id, 'user_id'): # untuk MessageService
             sender_id = message_obj.from_id.user_id
        message_id = message_obj.id if hasattr(message_obj, 'id') else None
        return {"timestamp": timestamp, "sender_id": sender_id, "message_id": message_id, "raw_text": message_obj.raw_text}

    def _parse_targets_from_signal_update(self, text_lines: List[str]) -> List[TargetInfo]:
        targets = []
        # Contoh: 🎯 Target 1 (13.34) HIT!
        target_pattern = re.compile(r"🎯\s*Target\s*(\d+)\s*\((\d+\.?\d*)\)\s*HIT!")
        for line in text_lines:
            match = target_pattern.search(line)
            if match:
                targets.append(TargetInfo(level=int(match.group(1)), price=float(match.group(2)), status="HIT"))
        return targets

    def _parse_stop_losses_from_signal_update(self, text_lines: List[str]) -> List[StopLossInfo]:
        stop_losses = []
        # Contoh: ⚠️ Stop Loss 1 (415.65) TRIGGERED!
        sl_pattern = re.compile(r"⚠️\s*Stop Loss\s*(\d+)\s*\((\d+\.?\d*)\)\s*TRIGGERED!")
        for line in text_lines:
            match = sl_pattern.search(line)
            if match:
                stop_losses.append(StopLossInfo(level=int(match.group(1)), price=float(match.group(2)), status="TRIGGERED"))
        return stop_losses

    def _parse_new_signal_targets_sl(self, lines: List[str]) -> Tuple[List[TargetInfo], List[StopLossInfo]]:
        targets = []
        stop_losses = []
        # Target 1         0.0198      +0.51%
        # Stop Loss 1    0.0194      -1.52%
        target_pattern = re.compile(r"Target\s+(\d+)\s+([\d.]+)\s+([+-]?[\d.]+)%")
        sl_pattern = re.compile(r"Stop Loss\s+(\d+)\s+([\d.]+)\s+([+-]?[\d.]+)%")

        for line in lines:
            target_match = target_pattern.match(line.strip())
            if target_match:
                targets.append(TargetInfo(
                    level=int(target_match.group(1)),
                    price=float(target_match.group(2)),
                    percentage_change=float(target_match.group(3))
                ))
            else:
                sl_match = sl_pattern.match(line.strip())
                if sl_match:
                    stop_losses.append(StopLossInfo(
                        level=int(sl_match.group(1)),
                        price=float(sl_match.group(2)),
                        percentage_change=float(sl_match.group(3))
                    ))
        return targets, stop_losses


    def parse_message(self, message_obj: Any) -> BaseMessage:
        """
        Menganalisis objek pesan Telethon dan mengembalikan objek data yang sesuai.
        Objek pesan bisa berupa telethon.tl.types.Message atau objek serupa.
        """
        common_attrs = self._extract_sender_and_timestamp(message_obj)
        text = common_attrs["raw_text"]
        lines = text.splitlines()
        first_line = lines[0] if lines else ""

        # 1. Signal Update
        # ✅ SIGNAL UPDATE: DEXEUSDT ✅ atau 🔴 SIGNAL UPDATE: BCHUSDT 🔴
        signal_update_match = re.match(r"^(✅|🔴)\s*SIGNAL UPDATE:\s*([A-Z0-9]+USDT)\s*(✅|🔴)", first_line)
        if signal_update_match:
            coin_pair = signal_update_match.group(2)
            targets_hit = self._parse_targets_from_signal_update(lines)
            sl_triggered = self._parse_stop_losses_from_signal_update(lines)
            update_type = ""
            if targets_hit: update_type = "TARGET_HIT"
            if sl_triggered: update_type = "STOP_LOSS_TRIGGERED" # Bisa juga keduanya

            return SignalUpdate(
                **common_attrs,
                coin_pair=coin_pair,
                targets_hit=targets_hit,
                stop_losses_triggered=sl_triggered,
                update_type=update_type
            )

        # 2. New Signal
        # 🆕 NEW SIGNAL: SUNUSDT 🆕
        new_signal_match = re.match(r"🆕\s*NEW SIGNAL:\s*([A-Z0-9]+USDT)\s*🆕", first_line)
        if new_signal_match:
            coin_pair = new_signal_match.group(1)
            risk_rank, risk_level, entry_price = None, None, None
            social_link, data_link = None, None
            targets, stop_losses = [], []

            # Regex untuk berbagai bagian
            risk_analysis_match = re.search(r"Volume\(24H\) Ranked:\s*(\S+)\s*Risk Level:\s*⚠️\s*(\w+)", text)
            if risk_analysis_match:
                risk_rank = risk_analysis_match.group(1)
                risk_level = risk_analysis_match.group(2)

            entry_match = re.search(r"Entry:\s*([\d.]+)", text)
            if entry_match:
                entry_price = float(entry_match.group(1))

            # Cari blok target & stop loss
            try:
                table_start_index = lines.index("----------------------------------------------") +1
                table_end_index = lines.index("----------------------------------------------", table_start_index)
                targets, stop_losses = self._parse_new_signal_targets_sl(lines[table_start_index:table_end_index])
            except ValueError: # Jika format tabel tidak ditemukan
                pass


            social_link_match = re.search(r"Cek Sentimen Sosial Media untuk \S+ \((https?://[^\s]+)\)", text)
            if social_link_match:
                social_link = social_link_match.group(1)

            data_link_match = re.search(r"Analisis Data Coinglass untuk \S+ \((https?://[^\s]+)\)", text)
            if data_link_match:
                data_link = data_link_match.group(1)

            return NewSignal(
                **common_attrs,
                coin_pair=coin_pair,
                risk_rank=risk_rank,
                risk_level=risk_level,
                entry_price=entry_price,
                targets=targets,
                stop_losses=stop_losses,
                social_media_link=social_link,
                data_analysis_link=data_link
            )

        # 3. Market Alert (ETH example)
        # ⚡⚡⚡ ETH price decreased -1.02% in the last 15 minutes.
        market_alert_match = re.match(r"⚡⚡⚡\s*([A-Z]+)\s*price\s*(increased|decreased)\s*([+-]?[\d.]+)%\s*in the last\s*(\d+)\s*minutes", first_line)
        if market_alert_match:
            coin = market_alert_match.group(1)
            # direction = market_alert_match.group(2) # increased or decreased
            percentage = float(market_alert_match.group(3))
            timeframe = int(market_alert_match.group(4))
            # Ambil seluruh pesan alert jika ada lebih dari satu baris (misal, versi bhs Inggris & Mandarin)
            alert_message = "\n".join(lines).strip()

            return MarketAlert(
                **common_attrs,
                coin=coin,
                price_change_percentage=percentage,
                timeframe_minutes=timeframe,
                alert_message=alert_message
            )

        # 4. Unstructured News (FTX example)
        # Coba deteksi apakah ini pesan dari pengirim tertentu (misal 'Dwi') dan bukan bot sistem
        # Ini contoh sederhana, mungkin perlu penyesuaian lebih lanjut
        if common_attrs["sender_id"] and not text.startswith("✅") and not text.startswith("🔴") and not text.startswith("🆕") and not text.startswith("⚡⚡⚡"):
             # Cek apakah pesan memiliki sumber seperti "Source: Crypto Insider"
            source_match = re.search(r"Source:\s*(.*)", text, re.IGNORECASE)
            source = source_match.group(1).strip() if source_match else None
            return UnstructuredMessage(**common_attrs, content=text, original_sender=source)


        # Default: jika tidak ada yang cocok, anggap sebagai pesan tidak terstruktur
        return UnstructuredMessage(**common_attrs, content=text)