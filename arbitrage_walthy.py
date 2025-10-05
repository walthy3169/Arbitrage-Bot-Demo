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
        self.setWindowTitle("Arbitrage by Walthy - Binance & KuCoin")
        self.setGeometry(200, 200, 600, 550)

        self.binance_api_key_input = QLineEdit()
        self.binance_secret_key_input = QLineEdit()
        self.kucoin_api_key_input = QLineEdit()
        self.kucoin_secret_key_input = QLineEdit()
        self.kucoin_passphrase_input = QLineEdit()

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Enter trade amount (e.g. 0.001 or 100)")

        self.amount_type_combo = QComboBox()
        self.amount_type_combo.addItems(["BTC", "USDT"])

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)

        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)

        self.init_ui()

        self.running = False
        self.commission_address = "PUT_YOUR_USDT_WALLET_ADDRESS_HERE"  # <-- EDIT THIS
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

        layout.addWidget(QLabel("Trade Amount:"))
        layout.addWidget(self.amount_input)
        layout.addWidget(QLabel("Amount Type:"))
        layout.addWidget(self.amount_type_combo)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("Status Log:"))
        layout.addWidget(self.status_log)

        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_bot)
        self.stop_btn.clicked.connect(self.stop_bot)

    def log(self, message):
        self.status_log.append(message)
        print(message)

    def start_bot(self):
        if self.running:
            self.log("Bot is already running.")
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
            QMessageBox.warning(self, "Error", "Please enter all API credentials.")
            return

        if not self.amount_str:
            QMessageBox.warning(self, "Error", "Please enter a trade amount.")
            return

        try:
            self.amount_value = float(self.amount_str)
            if self.amount_value <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid trade amount.")
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
            self.log("Connected to exchanges successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
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
        self.log("Bot stopped.")

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
                    self.log(f"Opportunity: Buy on Binance {binance_ask}, Sell on KuCoin {kucoin_bid}, Profit {profit_1:.2f}%")
                    self.execute_trade('binance', 'kucoin', symbol, binance_ask, kucoin_bid)
                elif profit_2 > min_profit_percent:
                    self.log(f"Opportunity: Buy on KuCoin {kucoin_ask}, Sell on Binance {binance_bid}, Profit {profit_2:.2f}%")
                    self.execute_trade('kucoin', 'binance', symbol, kucoin_ask, binance_bid)
                else:
                    self.log("No arbitrage opportunity right now.")

            except Exception as e:
                self.log(f"Error: {str(e)}")

            time.sleep(10)

    def execute_trade(self, buy_exchange, sell_exchange, symbol, buy_price, sell_price):
        try:
            amount = self.amount_value

            if self.amount_type == "USDT":
                btc_price = self.binance.fetch_ticker('BTC/USDT')['ask']
                amount = amount / btc_price
                self.log(f"{self.amount_value} USDT ≈ {amount:.6f} BTC will be used for the trade.")
            else:
                self.log(f"{amount} BTC will be used for the trade.")

            if amount < 0.0001:
                self.log("Trade amount too low, cancelled.")
                return

            commission_percent = 1  # 1% commission

            buy_ex = self.binance if buy_exchange == 'binance' else self.kucoin
            sell_ex = self.kucoin if sell_exchange == 'kucoin' else self.binance

            buy_order = buy_ex.create_market_buy_order(symbol, amount)
            self.log(f"{buy_exchange.capitalize()} - Market BUY order sent.")

            time.sleep(2)

            sell_order = sell_ex.create_market_sell_order(symbol, amount)
            self.log(f"{sell_exchange.capitalize()} - Market SELL order sent.")

            executed_buy_price = buy_order.get('average', buy_price)
            executed_sell_price = sell_order.get('average', sell_price)

            gross_profit = (executed_sell_price - executed_buy_price) * amount
            self.log(f"Executed buy: {executed_buy_price:.2f}, sell: {executed_sell_price:.2f}")
            self.log(f"Gross profit: {gross_profit:.6f} USDT")

            if gross_profit > 0:
                commission = gross_profit * commission_percent / 100
                self.send_commission(commission)
                self.log(f"Commission sent: {commission:.6f} USDT")
            else:
                self.log("Negative profit. No commission sent.")

        except Exception as e:
            self.log(f"Trade error: {str(e)}")

    def send_commission(self, commission_amount):
        try:
            withdraw_result = self.kucoin.withdraw(
                code='USDT',
                amount=round(commission_amount, 6),
                address=self.commission_address,
                network='TRC20'
            )
            self.log(f"✅ Commission sent: {commission_amount:.6f} USDT → {self.commission_address}")
            self.log(f"KuCoin withdraw result: {withdraw_result}")
        except Exception as e:
            self.log(f"❌ Commission sending error: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    bot = ArbitrageBot()
    bot.show()
    sys.exit(app.exec_())