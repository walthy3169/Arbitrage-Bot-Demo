import sys
import ccxt
import time
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QLineEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QTextEdit, QComboBox
)

class ArbitrageBot(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arbitraj Botu - Binance & KuCoin")
        self.setGeometry(200, 200, 600, 550)

        self.binance_api_key_input = QLineEdit()
        self.binance_secret_key_input = QLineEdit()
        self.kucoin_api_key_input = QLineEdit()
        self.kucoin_secret_key_input = QLineEdit()
        self.kucoin_passphrase_input = QLineEdit()

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("İşlem tutarını girin (ör: 0.001 veya 100)")

        self.amount_type_combo = QComboBox()
        self.amount_type_combo.addItems(["BTC", "USDT"])

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)

        self.start_btn = QPushButton("Başlat")
        self.stop_btn = QPushButton("Durdur")
        self.stop_btn.setEnabled(False)

        self.init_ui()

        self.running = False
        self.commission_address = "BURAYA_USDT_CUZDAN_ADRESINI_YAZ"  # <-- BUNU DÜZENLE
        self.bot_thread = None

    def init_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Binance API Key:"))
        layout.addWidget(self.binance_api_key_input)
        layout.addWidget(QLabel("Binance Secret Key:"))
        layout.addWidget(self.binance_secret_key_input)

        layout.addWidget(QLabel("KuCoin API Key:"))
        layout.addWidget(self.kucoin_api_key_input)
        layout.addWidget(QLabel("KuCoin Secret Key:"))
        layout.addWidget(self.kucoin_secret_key_input)
        layout.addWidget(QLabel("KuCoin Passphrase:"))
        layout.addWidget(self.kucoin_passphrase_input)

        layout.addWidget(QLabel("İşlem Tutarı:"))
        layout.addWidget(self.amount_input)
        layout.addWidget(QLabel("Tutar Cinsi:"))
        layout.addWidget(self.amount_type_combo)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("Durum Günlükleri:"))
        layout.addWidget(self.status_log)

        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_bot)
        self.stop_btn.clicked.connect(self.stop_bot)

    def log(self, message):
        self.status_log.append(message)
        print(message)

    def start_bot(self):
        if self.running:
            self.log("Bot zaten çalışıyor.")
            return

        self.binance_api_key = self.binance_api_key_input.text().strip()
        self.binance_secret_key = self.binance_secret_key_input.text().strip()
        self.kucoin_api_key = self.kucoin_api_key_input.text().strip()
        self.kucoin_secret_key = self.kucoin_secret_key_input.text().strip()
        self.kucoin_passphrase = self.kucoin_passphrase_input.text().strip()

        self.amount_str = self.amount_input.text().strip()
        self.amount_type = self.amount_type_combo.currentText()

        if not all([self.binance_api_key, self.binance_secret_key,
                    self.kucoin_api_key, self.kucoin_secret_key, self.kucoin_passphrase]):
            QMessageBox.warning(self, "Hata", "Lütfen tüm API bilgilerini eksiksiz girin.")
            return

        if not self.amount_str:
            QMessageBox.warning(self, "Hata", "Lütfen işlem tutarını girin.")
            return

        try:
            self.amount_value = float(self.amount_str)
            if self.amount_value <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, "Hata", "Geçerli bir işlem tutarı girin.")
            return

        try:
            self.binance = ccxt.binance({
                'apiKey': self.binance_api_key,
                'secret': self.binance_secret_key,
                'enableRateLimit': True,
            })
            self.kucoin = ccxt.kucoin({
                'apiKey': self.kucoin_api_key,
                'secret': self.kucoin_secret_key,
                'password': self.kucoin_passphrase,
                'enableRateLimit': True,
            })

            self.binance.load_markets()
            self.kucoin.load_markets()
            self.log("Borsalara başarıyla bağlanıldı.")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", str(e))
            return

        self.running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        self.running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log("Bot durduruldu.")

    def run_bot(self):
        symbol = 'BTC/USDT'
        min_profit_percent = 0.5

        while self.running:
            try:
                binance_ticker = self.binance.fetch_ticker(symbol)
                kucoin_ticker = self.kucoin.fetch_ticker(symbol)

                binance_bid = binance_ticker['bid']
                binance_ask = binance_ticker['ask']
                kucoin_bid = kucoin_ticker['bid']
                kucoin_ask = kucoin_ticker['ask']

                profit_1 = (kucoin_bid - binance_ask) / binance_ask * 100
                profit_2 = (binance_bid - kucoin_ask) / kucoin_ask * 100

                if profit_1 > min_profit_percent:
                    self.log(f"Fırsat: Binance al {binance_ask}, KuCoin sat {kucoin_bid}, Kar %{profit_1:.2f}")
                    self.execute_trade('binance', 'kucoin', symbol, binance_ask, kucoin_bid)
                elif profit_2 > min_profit_percent:
                    self.log(f"Fırsat: KuCoin al {kucoin_ask}, Binance sat {binance_bid}, Kar %{profit_2:.2f}")
                    self.execute_trade('kucoin', 'binance', symbol, kucoin_ask, binance_bid)
                else:
                    self.log("Şu an arbitraj fırsatı yok.")

            except Exception as e:
                self.log(f"Hata oluştu: {str(e)}")

            time.sleep(10)

    def execute_trade(self, buy_exchange, sell_exchange, symbol, buy_price, sell_price):
        try:
            amount = self.amount_value

            if self.amount_type == "USDT":
                btc_price = self.binance.fetch_ticker('BTC/USDT')['ask']
                amount = amount / btc_price
                self.log(f"{self.amount_value} USDT ≈ {amount:.6f} BTC olarak işleme alınacak.")
            else:
                self.log(f"{amount} BTC olarak işleme alınacak.")

            if amount < 0.0001:
                self.log("İşlem tutarı çok düşük, işlem iptal.")
                return

            commission_percent = 1  # %1 komisyon

            buy_ex = self.binance if buy_exchange == 'binance' else self.kucoin
            sell_ex = self.kucoin if sell_exchange == 'kucoin' else self.binance

            buy_order = buy_ex.create_market_buy_order(symbol, amount)
            self.log(f"{buy_exchange.capitalize()} - Market ALIM emri gönderildi.")

            time.sleep(2)

            sell_order = sell_ex.create_market_sell_order(symbol, amount)
            self.log(f"{sell_exchange.capitalize()} - Market SATIM emri gönderildi.")

            executed_buy_price = buy_order.get('average', buy_price)
            executed_sell_price = sell_order.get('average', sell_price)

            gross_profit = (executed_sell_price - executed_buy_price) * amount
            self.log(f"Gerçek alış: {executed_buy_price:.2f}, satış: {executed_sell_price:.2f}")
            self.log(f"Brüt kar: {gross_profit:.6f} USDT")

            if gross_profit > 0:
                commission = gross_profit * commission_percent / 100
                self.send_commission(commission)
                self.log(f"Komisyon gönderildi: {commission:.6f} USDT")
            else:
                self.log("Kar negatif. Komisyon gönderilmedi.")

        except Exception as e:
            self.log(f"İşlem hatası: {str(e)}")

    def send_commission(self, commission_amount):
        try:
            withdraw_result = self.kucoin.withdraw(
                code='USDT',
                amount=round(commission_amount, 6),
                address=self.commission_address,
                network='TRC20'
            )
            self.log(f"✅ Gerçek komisyon gönderildi: {commission_amount:.6f} USDT → {self.commission_address}")
            self.log(f"KuCoin işlem sonucu: {withdraw_result}")
        except Exception as e:
            self.log(f"❌ Komisyon gönderme hatası: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    bot = ArbitrageBot()
    bot.show()
    sys.exit(app.exec_())
