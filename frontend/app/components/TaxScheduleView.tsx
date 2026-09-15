import React, { useState, FormEvent, ChangeEvent } from 'react';
import { Header } from './Header';

type TaxScheduleViewProps = {
  transactions: any[];
  declarationType: string;
  userToken: string | null;
  setViewMode: (mode: 'dashboard' | 'chat' | 'ledger' | 'tax_schedule') => void;
  setShowSettingsModal: (show: boolean) => void;
  fetchTaxSchedulePeriods: (token: string) => Promise<void>;
  getTaxSchedulePeriods: () => any[];
  formatVND: (amount: number) => string;
  formatDateDisplay: (dateStr: string) => string;
};

export const TaxScheduleView: React.FC<TaxScheduleViewProps> = ({
  transactions,
  declarationType,
  userToken,
  setViewMode,
  setShowSettingsModal,
  fetchTaxSchedulePeriods,
  getTaxSchedulePeriods,
  formatVND,
  formatDateDisplay
}) => {
  // Modal & Payment form states
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState<any | null>(null);
  const [paymentPaidAmount, setPaymentPaidAmount] = useState("");
  const [paymentPaidDate, setPaymentPaidDate] = useState(new Date().toISOString().split('T')[0]);

  // Helpers
  const handleNumberChange = (
    e: ChangeEvent<HTMLInputElement>,
    setVal: (val: string) => void,
    setDisplayVal: (val: string) => void
  ) => {
    const input = e.target;
    const oldVal = input.value;
    const selectionStart = input.selectionStart || 0;

    let digitsBeforeCursor = 0;
    for (let i = 0; i < selectionStart; i++) {
      if (/\d/.test(oldVal[i])) {
        digitsBeforeCursor++;
      }
    }

    const raw = oldVal.replace(/\D/g, "");
    setVal(raw);

    const formatted = raw.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    setDisplayVal(formatted);

    setTimeout(() => {
      let newCursorPos = 0;
      let digitsSeen = 0;
      for (let i = 0; i < formatted.length; i++) {
        if (digitsSeen === digitsBeforeCursor) {
          break;
        }
        if (/\d/.test(formatted[i])) {
          digitsSeen++;
        }
        newCursorPos++;
      }
      input.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  };

  const handleOpenPaymentModal = (period: any) => {
    setSelectedPayment(period);
    const amountVal = period.paidAmount > 0 ? period.paidAmount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".") : "";
    setPaymentPaidAmount(amountVal);
    setPaymentPaidDate(period.paidDate || new Date().toISOString().split('T')[0]);
    setPaymentModalOpen(true);
  };

  const handleSavePayment = async (e: FormEvent) => {
    e.preventDefault();
    if (!userToken || !selectedPayment) return;

    const amountNum = parseFloat(paymentPaidAmount.replace(/\./g, '').replace(/,/g, ''));
    const parsedAmount = isNaN(amountNum) ? 0 : amountNum;

    try {
      const response = await fetch('/api/tax-payments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          supabase_token: userToken,
          period_key: selectedPayment.periodKey,
          due_date: selectedPayment.dueDate,
          tax_amount: selectedPayment.estimatedTax,
          paid_amount: parsedAmount,
          paid_date: paymentPaidDate || null
        })
      });

      if (response.ok) {
        alert("Cập nhật thông tin nộp thuế thành công!");
        fetchTaxSchedulePeriods(userToken);
        setPaymentModalOpen(false);
      } else {
        const errData = await response.json();
        alert(`Lỗi: ${errData.error || 'Không thể lưu thông tin nộp thuế.'}`);
      }
    } catch (err) {
      console.error(err);
      alert("Lỗi kết nối.");
    }
  };

  return (
    <div className="layout" style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <Header title="Lịch nộp thuế & Trạng thái đóng" iconClass="fa-solid fa-calendar-days" onBack={() => setViewMode('dashboard')} />
      <div style={{ flex: 1, overflowY: 'auto', padding: '2rem', backgroundColor: '#f8fafc' }}>
        <div style={{ maxWidth: '1000px', margin: '0 auto' }}>

          <div style={{ marginBottom: '1.25rem', padding: '12px 16px', background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', boxShadow: 'var(--shadow-sm)' }}>
            <div>
              <span style={{ fontSize: '0.9rem', color: '#64748b', fontWeight: '500' }}>Hình thức kê khai hiện tại:</span>
              <strong style={{ fontSize: '0.95rem', color: '#1e293b', marginLeft: '6px' }}>
                {declarationType === 'thang' && 'Kê khai theo Tháng'}
                {declarationType === 'quy' && 'Kê khai theo Quý'}
                {declarationType === 'lan_phat_sinh' && 'Kê khai theo Từng lần phát sinh'}
              </strong>
            </div>
            <button
              className='secondary-button'
              onClick={() => { setViewMode('dashboard'); setShowSettingsModal(true); }}
              style={{ width: 'auto', margin: 'auto 0', padding: '6px 12px', fontSize: '0.8rem', borderRadius: '6px', minHeight: 'auto', height: '30px' }}
            >
              Thay đổi hình thức
            </button>
          </div>

          <div className="ledger-table-container">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Kỳ kê khai</th>
                  <th>Doanh thu</th>
                  <th>Thuế dự kiến</th>
                  <th>Hạn nộp</th>
                  <th>Đã đóng</th>
                  <th>Ngày đóng</th>
                  <th>Trạng thái</th>
                  <th style={{ textAlign: 'center' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {getTaxSchedulePeriods().length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                      Chưa có dữ liệu giao dịch cho hình thức kê khai này. Hãy nhập thêm giao dịch trong Sổ thu chi.
                    </td>
                  </tr>
                ) : (
                  getTaxSchedulePeriods().map((period) => (
                    <tr key={period.periodKey}>
                      <td style={{ fontWeight: '500' }}>{period.periodLabel}</td>
                      <td style={{ textAlign: 'center' }}>{formatVND(period.revenue)}</td>
                      <td style={{ color: period.estimatedTax > 0 ? '#b45309' : 'inherit', fontWeight: period.estimatedTax > 0 ? '600' : 'normal', textAlign: 'center' }}>
                        {formatVND(period.estimatedTax)}
                      </td>
                      <td style={{ fontWeight: '500', textAlign: 'center' }}>{formatDateDisplay(period.dueDate)}</td>
                      <td style={{ color: period.paidAmount > 0 ? '#047857' : 'inherit', textAlign: 'center' }}>{formatVND(period.paidAmount)}</td>
                      <td style={{ textAlign: 'center' }}>{period.paidDate ? formatDateDisplay(period.paidDate) : '-'}</td>
                      <td>
                        <span className={`stat-badge ${period.status === 'paid' ? 'badge-green' :
                          period.status === 'partial' ? 'badge-yellow' :
                            period.status === 'unpaid' ? 'badge-red' : 'badge-grey'
                          }`}>
                          {period.status === 'paid' && 'Đã nộp'}
                          {period.status === 'partial' && 'Nộp thiếu'}
                          {period.status === 'unpaid' && 'Chưa nộp'}
                          {period.status === 'none' && 'Không phát sinh'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <button
                          className="primary-button"
                          style={{ padding: '6px 8px', fontSize: '0.8rem', borderRadius: '6px', minWidth: 'max-content', minHeight: 'auto', height: '30px' }}
                          onClick={() => handleOpenPaymentModal(period)}
                        >
                          Cập nhật nộp
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

        </div>
      </div>

      {/* Sub-modal Cập nhật thông tin đóng thuế */}
      {paymentModalOpen && selectedPayment && (
        <div className="glass-modal-overlay" style={{ zIndex: 1010 }}>
          <div className="glass-modal-card" style={{ maxWidth: '400px' }}>
            <div className="glass-modal-header">
              <h3><i className="fa-solid fa-credit-card"></i> Cập nhật đóng thuế</h3>
              <button className="glass-modal-close-btn" onClick={() => setPaymentModalOpen(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <form onSubmit={handleSavePayment}>
              <div className="glass-modal-body">
                <div className="dark-form">
                  <div className="dark-form-group">
                    <label>Kỳ kê khai</label>
                    <input type="text" value={selectedPayment.periodLabel} disabled style={{ backgroundColor: '#f1f5f9', cursor: 'not-allowed' }} />
                  </div>
                  <div className="dark-form-group">
                    <label>Số tiền thuế đã nộp (VNĐ)</label>
                    <input
                      type="text"
                      value={paymentPaidAmount}
                      onChange={(e) => handleNumberChange(e, setPaymentPaidAmount, setPaymentPaidAmount)}
                      placeholder="VD: 50.000"
                      required
                    />
                  </div>
                  <div className="dark-form-group">
                    <label>Ngày nộp thực tế</label>
                    <input
                      type="date"
                      value={paymentPaidDate}
                      onChange={(e) => setPaymentPaidDate(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>
              <div className="glass-modal-footer">
                <button type="button" className="glass-btn-secondary" onClick={() => setPaymentModalOpen(false)} style={{ padding: '8px 20px', borderRadius: '8px' }}>Hủy</button>
                <button type="submit" className="glass-btn-primary btn-purple-grad" style={{ padding: '8px 20px', borderRadius: '8px', border: 'none' }}>Lưu thông tin</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
