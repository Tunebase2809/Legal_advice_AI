import React, { useState, ChangeEvent, FormEvent } from 'react';
import { Header } from './Header';

type LedgerViewProps = {
  transactions: any[];
  userToken: string | null;
  setViewMode: (mode: 'dashboard' | 'chat' | 'ledger' | 'tax_schedule') => void;
  fetchTransactions: (token: string) => Promise<void>;
  formatVND: (amount: number) => string;
};

export const LedgerView: React.FC<LedgerViewProps> = ({
  transactions,
  userToken,
  setViewMode,
  fetchTransactions,
  formatVND
}) => {
  // Filter states
  const [ledgerFilterType, setLedgerFilterType] = useState<'all' | 'month' | 'day'>('all');
  const [ledgerFilterMonth, setLedgerFilterMonth] = useState(new Date().toISOString().substring(0, 7));
  const [ledgerFilterDay, setLedgerFilterDay] = useState(new Date().toISOString().split('T')[0]);
  const [ledgerFilterClass, setLedgerFilterClass] = useState<'all' | 'thu' | 'chi'>('all');

  // Form states
  const [ledgerAmount, setLedgerAmount] = useState("");
  const [ledgerDate, setLedgerDate] = useState(new Date().toISOString().split('T')[0]);
  const [ledgerType, setLedgerType] = useState<'thu' | 'chi'>('thu');
  const [ledgerDescription, setLedgerDescription] = useState("");
  const [editingTransactionId, setEditingTransactionId] = useState<string | null>(null);

  // OCR states
  const [isOcrLoading, setIsOcrLoading] = useState(false);

  // States cho loading và xóa giao dịch
  const [isTableLoading, setIsTableLoading] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [transactionToDelete, setTransactionToDelete] = useState<any | null>(null);

  // Helper number formatter input
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

  // Handlers
  const handleSaveTransaction = async (e: FormEvent) => {
    e.preventDefault();
    if (!userToken || !ledgerDate || !ledgerAmount) return;

    const amountVal = parseFloat(ledgerAmount.replace(/\./g, '').replace(/,/g, ''));
    if (isNaN(amountVal) || amountVal <= 0) {
      alert("Số tiền phải lớn hơn 0.");
      return;
    }
    const amountNum = ledgerType === 'chi' ? -amountVal : amountVal;

    setIsTableLoading(true);
    try {
      let response;
      if (editingTransactionId) {
        response = await fetch(`/api/transactions/${editingTransactionId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            supabase_token: userToken,
            date: ledgerDate,
            amount: amountNum,
            description: ledgerDescription
          })
        });
      } else {
        response = await fetch('/api/transactions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            supabase_token: userToken,
            date: ledgerDate,
            amount: amountNum,
            description: ledgerDescription
          })
        });
      }

      if (response.ok) {
        await fetchTransactions(userToken);
        setLedgerAmount("");
        setLedgerDescription("");
        setEditingTransactionId(null);
        setLedgerType('thu');
      } else {
        alert("Lỗi khi lưu giao dịch.");
      }
    } catch (err) {
      console.error(err);
      alert("Lỗi kết nối.");
    } finally {
      setIsTableLoading(false);
    }
  };

  const handleStartEditTransaction = (tx: any) => {
    setEditingTransactionId(tx.id);
    setLedgerDate(tx.date);
    const amountVal = parseFloat(tx.amount || 0);
    const isExpense = amountVal < 0;
    setLedgerType(isExpense ? 'chi' : 'thu');
    setLedgerAmount(Math.abs(amountVal).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "."));
    setLedgerDescription(tx.description);

    // Tự động cuộn trang lên phần Cập nhật thông tin giao dịch
    setTimeout(() => {
      document.getElementById('ledger-form-section')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 50);
  };

  const handleCancelEditTransaction = () => {
    setEditingTransactionId(null);
    setLedgerDate(new Date().toISOString().split('T')[0]);
    setLedgerAmount("");
    setLedgerDescription("");
    setLedgerType('thu');
  };

  const handleDeleteTransaction = (tx: any) => {
    setTransactionToDelete(tx);
    setDeleteModalOpen(true);
  };

  const handleConfirmDeleteTransaction = async () => {
    if (!transactionToDelete || !userToken) return;
    setDeleteModalOpen(false);
    setIsTableLoading(true);
    try {
      const response = await fetch(`/api/transactions/${transactionToDelete.id}?supabase_token=${userToken}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        await fetchTransactions(userToken);
        if (editingTransactionId === transactionToDelete.id) {
          handleCancelEditTransaction();
        }
      } else {
        alert("Lỗi khi xóa giao dịch.");
      }
    } catch (err) {
      console.error(err);
      alert("Lỗi kết nối.");
    } finally {
      setIsTableLoading(false);
      setTransactionToDelete(null);
    }
  };

  const handleOcrFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !userToken) return;

    const maxSizeBytes = 2 * 1024 * 1024; // 2MB
    if (file.size > maxSizeBytes) {
      alert("Kích thước tệp tin không được vượt quá 2MB.");
      e.target.value = '';
      return;
    }

    setIsOcrLoading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("supabase_token", userToken);

    try {
      const response = await fetch('/api/transactions/ocr', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (response.ok) {
        fetchTransactions(userToken);
        alert(data.message || "Tự động trích xuất và lưu giao dịch thành công!");
      } else {
        alert(data.error || "Gặp lỗi trong quá trình xử lý tệp tin.");
      }
    } catch (err) {
      console.error("Lỗi trích xuất OCR:", err);
      alert("Lỗi kết nối đến máy chủ khi xử lý tệp tin.");
    } finally {
      setIsOcrLoading(false);
      e.target.value = '';
    }
  };

  const handleDownloadTemplate = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const response = await fetch('/api/transactions/template');
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Không thể tải file mẫu.");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "mau_so_tay_giao_dich.xlsx");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error("Lỗi tải template:", err);
      alert(err.message || "Gặp lỗi khi tải tệp tin mẫu.");
    }
  };

  // Filter calculations
  const filteredTransactions = transactions.filter((tx: any) => {
    if (!tx.date) return false;

    let matchTime = true;
    if (ledgerFilterType === 'month') {
      matchTime = tx.date.substring(0, 7) === ledgerFilterMonth;
    } else if (ledgerFilterType === 'day') {
      matchTime = tx.date === ledgerFilterDay;
    }

    let matchClass = true;
    if (ledgerFilterClass === 'thu') {
      matchClass = parseFloat(tx.amount || 0) > 0;
    } else if (ledgerFilterClass === 'chi') {
      matchClass = parseFloat(tx.amount || 0) < 0;
    }

    return matchTime && matchClass;
  });

  const totalIncome = filteredTransactions
    .filter((tx: any) => parseFloat(tx.amount || 0) > 0)
    .reduce((sum: number, tx: any) => sum + parseFloat(tx.amount || 0), 0);

  const totalExpense = filteredTransactions
    .filter((tx: any) => parseFloat(tx.amount || 0) < 0)
    .reduce((sum: number, tx: any) => sum + Math.abs(parseFloat(tx.amount || 0)), 0);

  const balance = totalIncome - totalExpense;

  return (
    <div className="layout" style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <Header title="Sổ giao dịch Thu / Chi" iconClass="fa-solid fa-book" onBack={() => setViewMode('dashboard')} />
      <div style={{ flex: 1, overflowY: 'auto', scrollBehavior: 'smooth', padding: '2rem', backgroundColor: '#f8fafc' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

          <div className="ledger-layout">
            {/* OCR Upload section */}
            <div className="ocr-upload-zone" onClick={() => document.getElementById('ocr-file-input')?.click()}>
              <input
                type="file"
                id="ocr-file-input"
                style={{ display: 'none' }}
                accept=".xlsx,.xls,.csv,.pdf,image/*"
                onChange={handleOcrFileUpload}
                disabled={isOcrLoading}
              />
              {isOcrLoading ? (
                <div>
                  <i className="fa-solid fa-spinner fa-spin ocr-upload-icon" style={{ color: '#10b981' }}></i>
                  <div className="ocr-upload-text" style={{ color: '#10b981', fontWeight: 'bold' }}>
                    AI đang phân tích và chiết xuất thông tin giao dịch...
                  </div>
                </div>
              ) : (
                <div>
                  <i className="fa-solid fa-cloud-arrow-up ocr-upload-icon"></i>
                  <div className="ocr-upload-text">
                    Kéo thả hoặc <strong>bấm vào đây để tải lên</strong> hóa đơn mua hàng, file Excel doanh thu, ảnh hóa đơn...
                    <br />
                    <br />
                    <strong>(Dung lượng tối đa: 2MB)</strong>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', marginTop: '4px' }}>
                    Hỗ trợ Excel, PDF, TXT hoặc file ảnh hóa đơn để AI tự động trích xuất
                  </div>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '-10px', marginBottom: '15px' }}>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                style={{
                  backgroundColor: 'transparent',
                  border: '1px solid #10b981',
                  color: '#10b981',
                  borderRadius: '8px',
                  padding: '6px 12px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(16, 185, 129, 0.08)' }}
                onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
              >
                <i className="fa-solid fa-file-arrow-down"></i> Tải file mẫu Excel/CSV
              </button>
            </div>

            {/* Add/Edit inline form */}
            <div id="ledger-form-section" className="ledger-add-section">
              <h4 style={{ margin: '0 0 1rem 0' }}>
                <i className="fa-solid fa-pen-to-square"></i> {' '}
                {editingTransactionId ? "Cập nhật thông tin giao dịch" : "Thêm giao dịch mới thủ công"}
              </h4>
              <form onSubmit={handleSaveTransaction} className="ledger-inline-form">
                <div className="dark-form-group">
                  <label>Phân loại</label>
                  <div style={{ display: 'flex', gap: '4px', background: '#e2e8f0', padding: '3px', borderRadius: '8px', height: '44px', alignItems: 'center' }}>
                    <button
                      type="button"
                      onClick={() => setLedgerType('thu')}
                      style={{
                        flex: 1,
                        height: '100%',
                        border: 'none',
                        borderRadius: '6px',
                        background: ledgerType === 'thu' ? '#10b981' : 'transparent',
                        color: ledgerType === 'thu' ? '#fff' : '#64748b',
                        fontWeight: '600',
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px'
                      }}
                    >
                      <i className="fa-solid fa-circle-plus"></i> Thu
                    </button>
                    <button
                      type="button"
                      onClick={() => setLedgerType('chi')}
                      style={{
                        flex: 1,
                        height: '100%',
                        border: 'none',
                        borderRadius: '6px',
                        background: ledgerType === 'chi' ? '#ef4444' : 'transparent',
                        color: ledgerType === 'chi' ? '#fff' : '#64748b',
                        fontWeight: '600',
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px'
                      }}
                    >
                      <i className="fa-solid fa-circle-minus"></i> Chi
                    </button>
                  </div>
                </div>
                <div className="dark-form-group">
                  <label>Ngày giao dịch</label>
                  <input
                    type="date"
                    value={ledgerDate}
                    onChange={(e) => setLedgerDate(e.target.value)}
                    required
                  />
                </div>
                <div className="dark-form-group">
                  <label>Số tiền (VNĐ)</label>
                  <input
                    type="text"
                    value={ledgerAmount}
                    onChange={(e) => handleNumberChange(e, setLedgerAmount, setLedgerAmount)}
                    required
                    placeholder="VD: 500.000"
                  />
                </div>
                <div className="dark-form-group">
                  <label>Diễn giải / Chi tiết</label>
                  <input
                    type="text"
                    value={ledgerDescription}
                    onChange={(e) => setLedgerDescription(e.target.value)}
                    required
                    placeholder={ledgerType === 'chi' ? "Mô tả khoản chi (ví dụ: Nhập thiết bị)" : "Mô tả nguồn thu (ví dụ: Bán thiết bị)"}
                  />
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button type="submit" className="primary-button btn-green-grad" style={{ padding: '10px 14px', borderRadius: '8px', fontSize: '0.9rem', width: '100%', height: '44px', justifyContent: 'center' }}>
                    {editingTransactionId ? "Cập nhật" : "Lưu"}
                  </button>
                  {editingTransactionId && (
                    <button type="button" className="icon-button" onClick={handleCancelEditTransaction} style={{ backgroundColor: 'rgba(255,255,255,0.1)', color: 'rgb(239, 68, 68)', borderRadius: '8px', height: '44px', width: '44px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none' }} title="Hủy chỉnh sửa">
                      <i className="fa-solid fa-xmark"></i>
                    </button>
                  )}
                </div>
              </form>
            </div>

            {/* Summary Statistics Cards */}
            <div className="ledger-summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.25rem' }}>
              {/* Tổng thu */}
              <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '16px', padding: '16px', display: 'flex', alignItems: 'center', gap: '16px', boxShadow: 'var(--shadow-sm)' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem' }}>
                  <i className="fa-solid fa-arrow-down-long"></i>
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: '500', display: 'block' }}>Tổng Thu (Doanh thu)</span>
                  <strong style={{ fontSize: '1.2rem', color: '#1e293b', fontWeight: '700' }}>{formatVND(totalIncome)}</strong>
                </div>
              </div>

              {/* Tổng chi */}
              <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '16px', padding: '16px', display: 'flex', alignItems: 'center', gap: '16px', boxShadow: 'var(--shadow-sm)' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem' }}>
                  <i className="fa-solid fa-arrow-up-long"></i>
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: '500', display: 'block' }}>Tổng Chi (Chi phí)</span>
                  <strong style={{ fontSize: '1.2rem', color: '#1e293b', fontWeight: '700' }}>{formatVND(totalExpense)}</strong>
                </div>
              </div>

              {/* Số dư */}
              <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '16px', padding: '16px', display: 'flex', alignItems: 'center', gap: '16px', boxShadow: 'var(--shadow-sm)' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: balance >= 0 ? 'rgba(79, 70, 229, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: balance >= 0 ? '#4f46e5' : '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem' }}>
                  <i className="fa-solid fa-scale-balanced"></i>
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: '500', display: 'block' }}>Số dư (Thu nhập ròng)</span>
                  <strong style={{ fontSize: '1.2rem', color: balance >= 0 ? '#4f46e5' : '#ef4444', fontWeight: '700' }}>{formatVND(balance)}</strong>
                </div>
              </div>
            </div>

            {/* Transactions list */}
            <div className="ledger-table-container" style={{ position: 'relative' }}>
              {isTableLoading && (
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: 'rgba(255, 255, 255, 0.75)',
                  backdropFilter: 'blur(3px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 10,
                  borderRadius: '16px'
                }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                    <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#4f46e5' }}></i>
                    <span style={{ fontSize: '0.9rem', color: '#4f46e5', fontWeight: '600' }}>Đang cập nhật sổ nhật ký...</span>
                  </div>
                </div>
              )}
              <div style={{ padding: '12px 16px', fontWeight: 'bold', borderBottom: '1px solid var(--border-color)', background: '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Sổ nhật ký giao dịch</span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 'normal' }}>
                  Hiển thị: {filteredTransactions.length} / {transactions.length} giao dịch
                </span>
              </div>

              {/* Filter Controls Panel */}
              <div style={{ padding: '12px 16px', background: '#fff', borderBottom: '1px solid #e2e8f0', display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: '600', color: '#475569', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <i className="fa-solid fa-filter" style={{ color: '#4f46e5' }}></i> Bộ lọc:
                </span>
                <div style={{ display: 'flex', background: '#e2e8f0', padding: '2px', borderRadius: '8px', gap: '2px' }}>
                  <button
                    type="button"
                    onClick={() => setLedgerFilterType('all')}
                    style={{
                      border: 'none',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: ledgerFilterType === 'all' ? '#fff' : 'transparent',
                      color: ledgerFilterType === 'all' ? '#1e293b' : '#64748b',
                      fontWeight: ledgerFilterType === 'all' ? '600' : '500',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      boxShadow: ledgerFilterType === 'all' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    Tất cả
                  </button>
                  <button
                    type="button"
                    onClick={() => setLedgerFilterType('month')}
                    style={{
                      border: 'none',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: ledgerFilterType === 'month' ? '#fff' : 'transparent',
                      color: ledgerFilterType === 'month' ? '#1e293b' : '#64748b',
                      fontWeight: ledgerFilterType === 'month' ? '600' : '500',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      boxShadow: ledgerFilterType === 'month' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    Theo tháng
                  </button>
                  <button
                    type="button"
                    onClick={() => setLedgerFilterType('day')}
                    style={{
                      border: 'none',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: ledgerFilterType === 'day' ? '#fff' : 'transparent',
                      color: ledgerFilterType === 'day' ? '#1e293b' : '#64748b',
                      fontWeight: ledgerFilterType === 'day' ? '600' : '500',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      boxShadow: ledgerFilterType === 'day' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    Theo ngày
                  </button>
                </div>

                <div style={{ display: 'flex', background: '#e2e8f0', padding: '2px', borderRadius: '8px', gap: '2px' }}>
                  <button
                    type="button"
                    onClick={() => setLedgerFilterClass(ledgerFilterClass === 'thu' ? 'all' : 'thu')}
                    style={{
                      border: 'none',
                      padding: '4px 12px',
                      borderRadius: '6px',
                      background: ledgerFilterClass === 'thu' ? '#fff' : 'transparent',
                      color: ledgerFilterClass === 'thu' ? '#10b981' : '#64748b',
                      fontWeight: ledgerFilterClass === 'thu' ? '600' : '500',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      boxShadow: ledgerFilterClass === 'thu' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    THU
                  </button>
                  <button
                    type="button"
                    onClick={() => setLedgerFilterClass(ledgerFilterClass === 'chi' ? 'all' : 'chi')}
                    style={{
                      border: 'none',
                      padding: '4px 12px',
                      borderRadius: '6px',
                      background: ledgerFilterClass === 'chi' ? '#fff' : 'transparent',
                      color: ledgerFilterClass === 'chi' ? '#ef4444' : '#64748b',
                      fontWeight: ledgerFilterClass === 'chi' ? '600' : '500',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      boxShadow: ledgerFilterClass === 'chi' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    CHI
                  </button>
                </div>

                {ledgerFilterType === 'month' && (
                  <input
                    type="month"
                    value={ledgerFilterMonth}
                    onChange={(e) => setLedgerFilterMonth(e.target.value)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: '6px',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.8rem',
                      outline: 'none',
                      color: '#334155'
                    }}
                  />
                )}

                {ledgerFilterType === 'day' && (
                  <input
                    type="date"
                    value={ledgerFilterDay}
                    onChange={(e) => setLedgerFilterDay(e.target.value)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: '6px',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.8rem',
                      outline: 'none',
                      color: '#334155'
                    }}
                  />
                )}
              </div>

              {filteredTransactions.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Chưa có giao dịch nào phù hợp với bộ lọc.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="ledger-table">
                    <thead>
                      <tr>
                        <th>Ngày</th>
                        <th>Diễn giải</th>
                        <th>Số tiền</th>
                        <th style={{ width: '90px' }}>Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTransactions.map((tx) => {
                        const isExpense = parseFloat(tx.amount || 0) < 0;
                        return (
                          <tr key={tx.id} style={{ backgroundColor: editingTransactionId === tx.id ? 'rgba(139, 92, 246, 0.1)' : 'transparent' }}>
                            <td>{tx.date ? new Date(tx.date).toLocaleDateString('vi-VN') : ''}</td>
                            <td>
                              <span className={`stat-badge ${isExpense ? 'badge-red' : 'badge-green'}`} style={{ marginRight: '8px', padding: '2px 6px', fontSize: '0.75rem', borderRadius: '4px', display: 'inline-block' }}>
                                {isExpense ? 'Chi' : 'Thu'}
                              </span>
                              {tx.description}
                            </td>
                            <td style={{ fontWeight: 'bold', color: isExpense ? '#ef4444' : '#10b981' }}>
                              {isExpense ? `- ${formatVND(Math.abs(tx.amount || 0))}` : `+ ${formatVND(tx.amount || 0)}`}
                            </td>
                            <td>
                              <div className="ledger-actions">
                                <button className="ledger-action-btn btn-edit" onClick={() => handleStartEditTransaction(tx)} title="Sửa giao dịch">
                                  <i className="fa-solid fa-pencil"></i>
                                </button>
                                <button className="ledger-action-btn btn-delete" onClick={() => handleDeleteTransaction(tx)} title="Xóa giao dịch">
                                  <i className="fa-solid fa-trash-can"></i>
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

          </div>
        </div>
      </div>

      {/* Modal xác nhận xóa giao dịch */}
      {deleteModalOpen && transactionToDelete && (
        <div className="glass-modal-overlay" style={{ zIndex: 1010 }}>
          <div className="glass-modal-card" style={{ maxWidth: '450px' }}>
            <div className="glass-modal-header" style={{ borderBottom: '1px solid #fee2e2' }}>
              <h3 style={{ color: '#ef4444' }}><i className="fa-solid fa-triangle-exclamation"></i> Xác nhận xóa giao dịch</h3>
              <button className="glass-modal-close-btn" onClick={() => { setDeleteModalOpen(false); setTransactionToDelete(null); }}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <div className="glass-modal-body" style={{ padding: '20px', color: '#1e293b' }}>
              <p style={{ margin: '0 0 16px 0', fontSize: '0.95rem', fontWeight: '500' }}>Bạn có chắc chắn muốn xóa giao dịch này không? Hành động này không thể hoàn tác.</p>

              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '14px', fontSize: '0.9rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ color: '#64748b' }}>Ngày giao dịch:</span>
                  <strong style={{ color: '#334155' }}>{transactionToDelete.date ? new Date(transactionToDelete.date).toLocaleDateString('vi-VN') : ''}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ color: '#64748b' }}>Phân loại:</span>
                  <span className={`stat-badge ${parseFloat(transactionToDelete.amount || 0) < 0 ? 'badge-red' : 'badge-green'}`}>
                    {parseFloat(transactionToDelete.amount || 0) < 0 ? 'Khoản Chi' : 'Khoản Thu'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ color: '#64748b' }}>Số tiền:</span>
                  <strong style={{ color: parseFloat(transactionToDelete.amount || 0) < 0 ? '#ef4444' : '#10b981' }}>
                    {formatVND(Math.abs(transactionToDelete.amount || 0))}
                  </strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ color: '#64748b' }}>Diễn giải:</span>
                  <strong style={{ color: '#334155', wordBreak: 'break-all' }}>{transactionToDelete.description}</strong>
                </div>
              </div>
            </div>
            <div className="glass-modal-footer" style={{ justifyContent: 'flex-end', gap: '8px', padding: '12px 20px' }}>
              <button
                type="button"
                className="glass-btn-secondary"
                onClick={() => { setDeleteModalOpen(false); setTransactionToDelete(null); }}
              >
                Hủy
              </button>
              <button
                type="button"
                className="glass-btn-primary delete"
                onClick={handleConfirmDeleteTransaction}
              >
                <i className="fa-solid fa-trash-can"></i> Xóa
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
