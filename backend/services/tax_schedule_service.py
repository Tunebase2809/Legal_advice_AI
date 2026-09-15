import os
import requests
import threading
from datetime import datetime, date, timedelta, timezone
from services.encryption_service import EncryptionService
from services.tax_calculator import TaxCalculator

class TaxScheduleService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        if not self.url or not self.key:
            print("Warning: SUPABASE_URL or SUPABASE_ANON_KEY is not set in TaxScheduleService.")
        self.encryption_service = EncryptionService()
        self.tax_calculator = TaxCalculator()

    def _decrypt_amount(self, value) -> float:
        if value is None:
            return 0.0
        val_str = str(value).strip()
        if not val_str:
            return 0.0
            
        # Check if it's already a plain numeric string (legacy support)
        try:
            return float(val_str)
        except ValueError:
            pass
            
        # Try to decrypt using EncryptionService
        try:
            decrypted = self.encryption_service.decrypt_text(val_str)
            return float(decrypted)
        except Exception as e:
            print(f"Error decrypting tax payment amount: {e}")
            return 0.0

    def get_tax_payments(self, user_token):
        if not self.url or not self.key or not user_token:
            return []
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(
                f"{self.url}/rest/v1/tax_payments", 
                headers=headers
            )
            if response.status_code == 200:
                records = response.json()
                for r in records:
                    r["tax_amount"] = self._decrypt_amount(r.get("tax_amount"))
                    r["paid_amount"] = self._decrypt_amount(r.get("paid_amount"))
                return records
            else:
                print(f"Error fetching tax payments: {response.text}")
        except Exception as e:
            print(f"Exception fetching tax payments: {e}")
        return []

    def update_tax_payment(self, user_token, period_key, due_date, tax_amount, paid_amount, paid_date, record_id=None, is_insert=False):
        if not self.url or not self.key or not user_token:
            return False
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            enc_tax_amount = self.encryption_service.encrypt_text(str(tax_amount))
            enc_paid_amount = self.encryption_service.encrypt_text(str(paid_amount))
            
            payload = {
                "period_key": period_key,
                "due_date": due_date,
                "tax_amount": enc_tax_amount,
                "paid_amount": enc_paid_amount,
                "paid_date": paid_date if paid_date else None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if record_id:
                response = requests.patch(
                    f"{self.url}/rest/v1/tax_payments?id=eq.{record_id}",
                    headers=headers,
                    json=payload
                )
            elif is_insert:
                response = requests.post(
                    f"{self.url}/rest/v1/tax_payments",
                    headers=headers,
                    json=payload
                )
            else:
                # Check if it already exists
                check_resp = requests.get(
                    f"{self.url}/rest/v1/tax_payments?period_key=eq.{period_key}",
                    headers=headers
                )
                data = check_resp.json() if check_resp.status_code == 200 else []
                
                if data and len(data) > 0:
                    record_id = data[0]["id"]
                    response = requests.patch(
                        f"{self.url}/rest/v1/tax_payments?id=eq.{record_id}",
                        headers=headers,
                        json=payload
                    )
                else:
                    response = requests.post(
                        f"{self.url}/rest/v1/tax_payments",
                        headers=headers,
                        json=payload
                    )
            return response.status_code in (200, 201, 204)
        except Exception as e:
            print(f"Exception updating tax payment: {e}")
        return False

    def is_holiday(self, date) -> bool:
        m = date.month
        d = date.day
        
        # Ngày lễ cố định Việt Nam (Dương lịch)
        if m == 1 and d == 1: return True # Tết Dương lịch
        if m == 4 and d == 30: return True # Giải phóng miền Nam
        if m == 5 and d == 1: return True # Quốc tế Lao động
        if m == 9 and d == 2: return True # Quốc khánh
        if m == 9 and d == 3: return True # Ngày nghỉ Quốc khánh bổ sung
        
        # Thứ 7 (5), Chủ nhật (6) in python (0 = Monday, 6 = Sunday)
        if date.weekday() in (5, 6): return True
        
        return False

    def get_adjusted_due_date(self, date_str: str) -> str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return date_str
            
        while self.is_holiday(d):
            d += timedelta(days=1)
            
        return d.strftime("%Y-%m-%d")

    def get_tax_schedule_periods(self, transactions, declaration_type, business_category, tax_payments, tax_rates, user_token=None):
        periods = []
        
        # Helper get category rates
        rate_info = tax_rates.get(business_category, {})
        gtgt_rate = rate_info.get("gtgt", 0.0)
        tncn_rate = rate_info.get("tncn", 0.0)
        
        # Chỉ lấy giao dịch doanh thu (thu nhập dương) để tính thuế
        revenue_transactions = [tx for tx in transactions if float(tx.get("amount") or 0) > 0]
        
        # Tính tổng doanh thu tích lũy trong năm hiện tại để áp dụng các ngưỡng tự động
        current_year_now = date.today().year
        total_annual_revenue_now = 0
        for tx in revenue_transactions:
            if tx.get("date") and tx["date"].startswith(str(current_year_now)):
                try:
                    total_annual_revenue_now += float(tx.get("amount") or 0)
                except ValueError:
                    pass
                    
        # Parse declaration_type: e.g. "quy_doanh_thu" -> cycle="quy", method="doanh_thu"
        parts = declaration_type.split('_', 1) if declaration_type else ['quy']
        cycle = parts[0]
        method = parts[1] if len(parts) > 1 else 'doanh_thu'
        
        # Ngưỡng 1: Tự động khóa phương pháp 'thu_nhap' nếu doanh thu năm > 3 tỷ
        if total_annual_revenue_now > self.tax_calculator.revenue_milestones["net_level_1"]:
            method = 'thu_nhap'
            
        # Tự động điều chỉnh chu kỳ kê khai theo quy định pháp luật dựa trên doanh thu:
        # - Trên 50 tỷ bắt buộc kê khai theo Tháng
        # - Dưới 50 tỷ (nếu đang khai định kỳ) bắt buộc kê khai theo Quý
        auto_switched_to_monthly = False
        auto_switched_to_quarterly = False
        if cycle in ('quy', 'thang'):
            if total_annual_revenue_now > self.tax_calculator.revenue_milestones["net_level_2"]:
                if cycle == 'quy':
                    cycle = 'thang'
                    auto_switched_to_monthly = True
            else:
                if cycle == 'thang':
                    cycle = 'quy'
                    auto_switched_to_quarterly = True

        def get_annual_revenue_for_year(year):
            sum_val = 0
            for tx in revenue_transactions:
                if not tx.get("date"):
                    continue
                try:
                    y = int(tx["date"].split("-")[0])
                    if y == year:
                        sum_val += float(tx.get("amount") or 0)
                except ValueError:
                    pass
            return sum_val

        def get_expenses_for_period(period_key, is_quarter=False):
            sum_val = 0
            for tx in transactions:
                if not tx.get("date") or float(tx.get("amount") or 0) >= 0:
                    continue
                if is_quarter:
                    # period_key format: YYYY-Q1
                    year, month_str = tx["date"].split("-")[:2]
                    try:
                        q = (int(month_str) + 2) // 3
                        tx_period_key = f"{year}-Q{q}"
                    except ValueError:
                        continue
                else:
                    # period_key format: YYYY-MM
                    tx_period_key = tx["date"][:7]
                if tx_period_key == period_key:
                    sum_val += abs(float(tx.get("amount") or 0))
            return sum_val

        if cycle == 'thang':
            groups = {}
            for tx in revenue_transactions:
                if not tx.get("date"):
                    continue
                period_key = tx["date"][:7] # YYYY-MM
                if period_key not in groups:
                    groups[period_key] = []
                groups[period_key].append(tx)
                
            # Sắp xếp các kỳ theo thứ tự thời gian tăng dần để cộng dồn doanh thu chính xác
            sorted_keys = sorted(groups.keys())
            cumulative_revenue_year = {}
            
            for period_key in sorted_keys:
                txs = groups[period_key]
                revenue = sum(float(tx.get("amount") or 0) for tx in txs)
                year_str, month_str = period_key.split("-")
                year = int(year_str)
                month = int(month_str)
                
                if year not in cumulative_revenue_year:
                    cumulative_revenue_year[year] = 0.0
                
                cumulative_rev_start = cumulative_revenue_year[year]
                cumulative_rev_end = cumulative_rev_start + revenue
                cumulative_revenue_year[year] = cumulative_rev_end
                
                expenses = get_expenses_for_period(period_key, is_quarter=False)
                
                # Tính toán thuế
                gtgt_tax = revenue * gtgt_rate
                
                if cumulative_rev_end <= self.tax_calculator.revenue_milestones["exemption"]:
                    # Dưới 1 tỷ được miễn thuế
                    estimated_tax = 0.0
                else:
                    if method == 'thu_nhap':
                        # Thuế TNCN tính trên thu nhập ròng với thuế suất lũy tiến
                        taxable_income = max(0.0, revenue - expenses)
                        if cumulative_rev_end <= self.tax_calculator.revenue_milestones["net_level_1"]:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_1"]
                        elif cumulative_rev_end <= self.tax_calculator.revenue_milestones["net_level_2"]:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_2"]
                        else:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_3"]
                        tncn_tax = taxable_income * tncn_rate_net
                        estimated_tax = gtgt_tax + tncn_tax
                    else:
                        # Thuế TNCN tính trên phần doanh thu vượt 1 tỷ
                        tncn_tax = max(0.0, cumulative_rev_end - self.tax_calculator.revenue_milestones["exemption"]) * tncn_rate - max(0.0, cumulative_rev_start - self.tax_calculator.revenue_milestones["exemption"]) * tncn_rate
                        estimated_tax = gtgt_tax + tncn_tax
                
                next_year = year
                next_month = month + 1
                if next_month > 12:
                    next_month = 1
                    next_year = year + 1
                    
                base_due_date_str = f"{next_year}-{str(next_month).zfill(2)}-20"
                due_date = self.get_adjusted_due_date(base_due_date_str)
                
                payment_record = next((p for p in tax_payments if p.get("period_key") == period_key), None)
                paid_amount = float(payment_record.get("paid_amount") or 0) if payment_record else 0.0
                paid_date = payment_record.get("paid_date") if payment_record else None
                
                # Tự động lưu/cập nhật vào database nếu có user_token
                if user_token:
                    if not payment_record:
                        threading.Thread(
                            target=self.update_tax_payment,
                            args=(user_token, period_key, due_date, estimated_tax, 0.0, None),
                            kwargs={"is_insert": True}
                        ).start()
                    elif abs(float(payment_record.get("tax_amount") or 0) - estimated_tax) > 0.01:
                        threading.Thread(
                            target=self.update_tax_payment,
                            args=(user_token, period_key, due_date, estimated_tax, paid_amount, paid_date),
                            kwargs={"record_id": payment_record.get("id")}
                        ).start()
                
                status = 'unpaid'
                if estimated_tax == 0:
                    status = 'none'
                elif paid_amount >= estimated_tax:
                    status = 'paid'
                elif paid_amount > 0:
                    status = 'partial'
                    
                periods.append({
                    "periodKey": period_key,
                    "periodLabel": f"Tháng {month_str}/{year}",
                    "revenue": revenue,
                    "expenses": expenses,
                    "estimatedTax": estimated_tax,
                    "dueDate": due_date,
                    "paidAmount": paid_amount,
                    "paidDate": paid_date,
                    "status": status,
                    "transactionsList": txs,
                    "autoSwitchedToMonthly": auto_switched_to_monthly,
                    "autoSwitchedToQuarterly": auto_switched_to_quarterly
                })
            # Sắp xếp các kỳ mới nhất lên đầu
            periods.reverse()

        elif cycle == 'quy':
            groups = {}
            for tx in revenue_transactions:
                if not tx.get("date"):
                    continue
                year, month_str = tx["date"].split("-")[:2]
                month = int(month_str)
                q = (month + 2) // 3
                period_key = f"{year}-Q{q}"
                if period_key not in groups:
                    groups[period_key] = []
                groups[period_key].append(tx)
                
            sorted_keys = sorted(groups.keys())
            cumulative_revenue_year = {}
            
            for period_key in sorted_keys:
                txs = groups[period_key]
                revenue = sum(float(tx.get("amount") or 0) for tx in txs)
                year_str, q_str = period_key.split("-Q")
                year = int(year_str)
                q = int(q_str)
                
                if year not in cumulative_revenue_year:
                    cumulative_revenue_year[year] = 0.0
                
                cumulative_rev_start = cumulative_revenue_year[year]
                cumulative_rev_end = cumulative_rev_start + revenue
                cumulative_revenue_year[year] = cumulative_rev_end
                
                expenses = get_expenses_for_period(period_key, is_quarter=True)
                
                # Tính toán thuế
                gtgt_tax = revenue * gtgt_rate
                
                if cumulative_rev_end <= self.tax_calculator.revenue_milestones["exemption"]:
                    estimated_tax = 0.0
                else:
                    if method == 'thu_nhap':
                        taxable_income = max(0.0, revenue - expenses)
                        if cumulative_rev_end <= self.tax_calculator.revenue_milestones["net_level_1"]:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_1"]
                        elif cumulative_rev_end <= self.tax_calculator.revenue_milestones["net_level_2"]:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_2"]
                        else:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_3"]
                        tncn_tax = taxable_income * tncn_rate_net
                        estimated_tax = gtgt_tax + tncn_tax
                    else:
                        tncn_tax = max(0.0, cumulative_rev_end - self.tax_calculator.revenue_milestones["exemption"]) * tncn_rate - max(0.0, cumulative_rev_start - self.tax_calculator.revenue_milestones["exemption"]) * tncn_rate
                        estimated_tax = gtgt_tax + tncn_tax
                
                base_due_date_str = ""
                if q == 1:
                    base_due_date_str = f"{year}-04-30"
                elif q == 2:
                    base_due_date_str = f"{year}-07-31"
                elif q == 3:
                    base_due_date_str = f"{year}-10-31"
                else:
                    base_due_date_str = f"{year + 1}-01-31"
                due_date = self.get_adjusted_due_date(base_due_date_str)
                
                payment_record = next((p for p in tax_payments if p.get("period_key") == period_key), None)
                paid_amount = float(payment_record.get("paid_amount") or 0) if payment_record else 0.0
                paid_date = payment_record.get("paid_date") if payment_record else None
                
                # Tự động lưu/cập nhật vào database nếu có user_token
                if user_token:
                    if not payment_record:
                        threading.Thread(
                            target=self.update_tax_payment,
                            args=(user_token, period_key, due_date, estimated_tax, 0.0, None),
                            kwargs={"is_insert": True}
                        ).start()
                    elif abs(float(payment_record.get("tax_amount") or 0) - estimated_tax) > 0.01:
                        threading.Thread(
                            target=self.update_tax_payment,
                            args=(user_token, period_key, due_date, estimated_tax, paid_amount, paid_date),
                            kwargs={"record_id": payment_record.get("id")}
                        ).start()
                
                status = 'unpaid'
                if estimated_tax == 0:
                    status = 'none'
                elif paid_amount >= estimated_tax:
                    status = 'paid'
                elif paid_amount > 0:
                    status = 'partial'
                    
                periods.append({
                    "periodKey": period_key,
                    "periodLabel": f"Quý {q}/{year}",
                    "revenue": revenue,
                    "expenses": expenses,
                    "estimatedTax": estimated_tax,
                    "dueDate": due_date,
                    "paidAmount": paid_amount,
                    "paidDate": paid_date,
                    "status": status,
                    "transactionsList": txs,
                    "autoSwitchedToMonthly": auto_switched_to_monthly,
                    "autoSwitchedToQuarterly": auto_switched_to_quarterly
                })
            periods.reverse()
            
        else:
            # Giao dịch phát sinh (không thường xuyên)
            sorted_txs = sorted(revenue_transactions, key=lambda x: x.get("date", ""))
            cumulative_revenue_year = {}
            
            for tx in sorted_txs:
                if not tx.get("date"):
                    continue
                period_key = tx.get("id")
                revenue = float(tx.get("amount") or 0)
                period_year = int(tx["date"].split("-")[0])
                
                if period_year not in cumulative_revenue_year:
                    cumulative_revenue_year[period_year] = 0.0
                
                cumulative_rev_start = cumulative_revenue_year[period_year]
                cumulative_rev_end = cumulative_rev_start + revenue
                cumulative_revenue_year[period_year] = cumulative_rev_end
                
                expenses = 0.0
                
                gtgt_tax = revenue * gtgt_rate
                
                if cumulative_rev_end <= self.tax_calculator.revenue_milestones["exemption"]:
                    estimated_tax = 0.0
                else:
                    if method == 'thu_nhap':
                        if cumulative_rev_end <= self.tax_calculator.revenue_milestones["net_level_1"]:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_1"]
                        elif cumulative_rev_end <= self.tax_calculator.revenue_milestones["net_level_2"]:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_2"]
                        else:
                            tncn_rate_net = self.tax_calculator.tncn_rates_net["level_3"]
                        estimated_tax = gtgt_tax + revenue * tncn_rate_net
                    else:
                        tncn_tax = max(0.0, cumulative_rev_end - self.tax_calculator.revenue_milestones["exemption"]) * tncn_rate - max(0.0, cumulative_rev_start - self.tax_calculator.revenue_milestones["exemption"]) * tncn_rate
                        estimated_tax = gtgt_tax + tncn_tax
                
                tx_date = datetime.strptime(tx["date"], "%Y-%m-%d").date()
                base_due_date_str = (tx_date + timedelta(days=10)).strftime("%Y-%m-%d")
                due_date = self.get_adjusted_due_date(base_due_date_str)
                
                payment_record = next((p for p in tax_payments if p.get("period_key") == period_key), None)
                paid_amount = float(payment_record.get("paid_amount") or 0) if payment_record else 0.0
                paid_date = payment_record.get("paid_date") if payment_record else None
                
                # Tự động lưu/cập nhật vào database nếu có user_token
                if user_token:
                    if not payment_record:
                        threading.Thread(
                            target=self.update_tax_payment,
                            args=(user_token, period_key, due_date, estimated_tax, 0.0, None),
                            kwargs={"is_insert": True}
                        ).start()
                    elif abs(float(payment_record.get("tax_amount") or 0) - estimated_tax) > 0.01:
                        threading.Thread(
                            target=self.update_tax_payment,
                            args=(user_token, period_key, due_date, estimated_tax, paid_amount, paid_date),
                            kwargs={"record_id": payment_record.get("id")}
                        ).start()
                
                status = 'unpaid'
                if estimated_tax == 0:
                    status = 'none'
                elif paid_amount >= estimated_tax:
                    status = 'paid'
                elif paid_amount > 0:
                    status = 'partial'
                
                # Format date to display DD/MM/YYYY
                parts = tx["date"].split('-')
                date_display = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else tx["date"]
                
                periods.append({
                    "periodKey": period_key,
                    "periodLabel": f"Giao dịch {date_display} - {tx.get('description', '')[:20]}{'...' if len(tx.get('description', '')) > 20 else ''}",
                    "revenue": revenue,
                    "expenses": expenses,
                    "estimatedTax": estimated_tax,
                    "dueDate": due_date,
                    "paidAmount": paid_amount,
                    "paidDate": paid_date,
                    "status": status,
                    "transactionsList": [tx],
                    "autoSwitchedToMonthly": auto_switched_to_monthly,
                    "autoSwitchedToQuarterly": auto_switched_to_quarterly
                })
            periods.reverse()
            
        return periods
