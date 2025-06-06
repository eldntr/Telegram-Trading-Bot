# telegram/parser.py
import re
from datetime import datetime
from typing import Any, List, Tuple

from .models import (
    SignalUpdate, NewSignal, MarketAlert, UnstructuredMessage,
    TargetInfo, StopLossInfo, BaseMessage, DailyRecap
)

class TelegramMessageParser:
    """Menganalisis objek pesan Telethon dan mengembalikannya sebagai model data terstruktur."""

    def _extract_common_attributes(self, message_obj: Any) -> dict:
        return {
            "timestamp": getattr(message_obj, 'date', datetime.now()),
            "sender_id": getattr(message_obj, 'sender_id', None),
            "message_id": getattr(message_obj, 'id', None),
            "raw_text": getattr(message_obj, 'raw_text', ''),
        }

    def parse_message(self, message_obj: Any) -> BaseMessage:
        if not message_obj or not getattr(message_obj, 'raw_text', None):
            return UnstructuredMessage(
                raw_text="[Pesan Media atau Aksi: Tanpa konten teks]",
                timestamp=getattr(message_obj, 'date', datetime.now()),
                sender_id=getattr(message_obj, 'sender_id', None),
                message_id=getattr(message_obj, 'id', None),
                content="[Pesan Media atau Aksi: Tanpa konten teks]",
            )

        common_attrs = self._extract_common_attributes(message_obj)
        text = common_attrs["raw_text"]
        lines = text.splitlines()
        first_line = lines[0].strip() if lines else ""

        parsers = [
            self._try_parse_daily_recap,
            self._try_parse_new_signal_alert,
            self._try_parse_new_signal,
            self._try_parse_signal_update,
            self._try_parse_market_alert
        ]
        for parser_func in parsers:
            if parsed_message := parser_func(first_line, text, lines, common_attrs):
                return parsed_message

        source_match = re.search(r"Source:\s*(.*)", text, re.IGNORECASE)
        source = source_match.group(1).strip() if source_match else None
        return UnstructuredMessage(**common_attrs, content=text, original_sender=source)

    # --- METODE HELPER YANG HILANG DITAMBAHKAN KEMBALI ---
    def _parse_targets_and_sl_from_update(self, lines: List[str]) -> Tuple[List[TargetInfo], List[StopLossInfo]]:
        """Mem-parsing target dan stop-loss dari pesan pembaruan sinyal."""
        targets, stop_losses = [], []
        target_pattern = re.compile(r"🎯\s*Target\s*(\d+)\s*\((\d+\.?\d*)\)\s*HIT!")
        sl_pattern = re.compile(r"⚠️\s*Stop Loss\s*(\d+)\s*\((\d+\.?\d*)\)\s*TRIGGERED!")
        for line in lines:
            if t_match := target_pattern.search(line):
                targets.append(TargetInfo(level=int(t_match.group(1)), price=float(t_match.group(2)), status="HIT"))
            if sl_match := sl_pattern.search(line):
                stop_losses.append(StopLossInfo(level=int(sl_match.group(1)), price=float(sl_match.group(2)), status="TRIGGERED"))
        return targets, stop_losses

    def _parse_targets_and_sl_from_new_signal(self, lines: List[str]) -> Tuple[List[TargetInfo], List[StopLossInfo]]:
        """Mem-parsing target dan stop-loss dari pesan sinyal baru."""
        targets, stop_losses = [], []
        target_pattern = re.compile(r"Target\s+(\d+)\s+([\d.]+)\s+([+-]?[\d.]+)%")
        sl_pattern = re.compile(r"Stop Loss\s+(\d+)\s+([\d.]+)\s+([+-]?[\d.]+)%")
        for line in lines:
            if t_match := target_pattern.search(line):
                targets.append(TargetInfo(level=int(t_match.group(1)), price=float(t_match.group(2)), percentage_change=float(t_match.group(3))))
            elif sl_match := sl_pattern.search(line):
                stop_losses.append(StopLossInfo(level=int(sl_match.group(1)), price=float(sl_match.group(2)), percentage_change=float(sl_match.group(3))))
        return targets, stop_losses

    # --- FUNGSI PARSER UTAMA ---
    def _try_parse_daily_recap(self, first_line, text, lines, common_attrs):
        if "DAILY RECAP" in first_line:
            date_range_match = re.search(r'(\d{2}/\d{2}-\d{2}/\d{2})', first_line)
            recap = DailyRecap(**common_attrs, date_range=date_range_match.group(1) if date_range_match else None)
            patterns = {
                "target_1": r"✅ Hitted target 1:\s*(.*)", "target_2": r"✅ Hitted target 2:\s*(.*)",
                "target_3": r"✅ Hitted target 3:\s*(.*)", "target_4": r"✅ Hitted target 4:\s*(.*)",
            }
            for line in lines:
                for key, pattern in patterns.items():
                    if match := re.match(pattern, line.strip()):
                        recap.targets_hit[key] = [coin.strip() for coin in match.group(1).split(',')]
                        break
                if match := re.match(r"➡️ Running:\s*(.*)", line.strip()):
                    recap.running_signals = [coin.strip() for coin in match.group(1).split(',')]
                elif match := re.match(r"🛑 Hitted stop loss:\s*(.*)", line.strip()):
                    recap.stop_losses_hit = [coin.strip() for coin in match.group(1).split(',')]
            if total_match := re.search(r"Total Signals:\s*(\d+)", text): recap.total_signals = int(total_match.group(1))
            if tp_match := re.search(r"Hitted Take-Profits:\s*(\d+)", text): recap.total_take_profits = int(tp_match.group(1))
            if sl_match := re.search(r"Hitted Stop-Losses:\s*(\d+)", text): recap.total_stop_losses = int(sl_match.group(1))
            return recap
        return None

    def _try_parse_new_signal_alert(self, first_line, text, lines, common_attrs):
        if first_line == "🆕 NEW SIGNAL 🆕":
            pattern = re.compile(r"(?:❗❗❗|⚡⚡⚡)\s*([A-Z]+)\s*price\s*(?:amplitude is|decreased)\s*([+-]?[\d.]+)%\s*in the last\s*(\d+)\s*minutes")
            if match := pattern.search(text):
                return MarketAlert(**common_attrs, coin=match.group(1), price_change_percentage=float(match.group(2)), timeframe_minutes=int(match.group(3)), alert_message=text.strip())
        return None

    def _try_parse_new_signal(self, first_line, text, lines, common_attrs):
        if match := re.match(r"🆕\s*NEW SIGNAL:\s*([A-Z0-9]+USDT)\s*🆕", first_line):
            risk_rank = (re.search(r"Volume\(24H\) Ranked:\s*(\S+)", text) or [None, None])[1]
            risk_level = (re.search(r"Risk Level:\s*(?:🟢|⚠️)\s*(\w+)", text) or [None, None])[1]
            entry_price = float((re.search(r"Entry:\s*([\d.]+)", text) or [None, 0])[1])
            signal = NewSignal(**common_attrs, coin_pair=match.group(1), risk_rank=risk_rank, risk_level=risk_level, entry_price=entry_price)
            try:
                indices = [i for i, line in enumerate(lines) if "---" in line]
                if len(indices) >= 3:
                    signal.targets, signal.stop_losses = self._parse_targets_and_sl_from_new_signal(lines[indices[1] + 1:indices[2]])
            except (ValueError, IndexError): pass
            return signal
        return None

    def _try_parse_signal_update(self, first_line, text, lines, common_attrs):
        if match := re.match(r"^(✅|🔴)\s*SIGNAL UPDATE:\s*([A-Z0-9]+USDT)\s*(✅|🔴)", first_line):
            targets_hit, sl_triggered = self._parse_targets_and_sl_from_update(lines)
            return SignalUpdate(**common_attrs, coin_pair=match.group(2), targets_hit=targets_hit, stop_losses_triggered=sl_triggered, update_type="TARGET_HIT" if targets_hit else "STOP_LOSS_TRIGGERED")
        return None

    def _try_parse_market_alert(self, first_line, text, lines, common_attrs):
        if match := re.match(r"⚡⚡⚡\s*([A-Z]+)\s*price\s*(?:increased|decreased)\s*([+-]?[\d.]+)%\s*in the last\s*(\d+)\s*minutes", first_line):
            return MarketAlert(**common_attrs, coin=match.group(1), price_change_percentage=float(match.group(3)), timeframe_minutes=int(match.group(4)), alert_message="\n".join(lines).strip())
        return None