import React, { FormEvent, useEffect } from 'react';

type DashboardViewProps = {
  transactions: any[];
  businessCategory: string;
  businessName: string;
  setViewMode: (mode: 'dashboard' | 'chat' | 'ledger' | 'tax_schedule') => void;
  setShowSettingsModal: (show: boolean) => void;
  getTaxDeadlineInfo: () => any;
  formatVND: (amount: number) => string;
  handleCancelEditTransaction: () => void;
  showTaxDetailModal: boolean;
  setShowTaxDetailModal: (show: boolean) => void;
  handleSignOut: () => void;
  showSettingsModal: boolean;
  isSavingSettings: boolean;
  handleSaveSettings: (e: FormEvent) => Promise<void>;
  setBusinessName: (name: string) => void;
  setBusinessCategory: (cat: string) => void;
  declarationType: string;
  setDeclarationType: (type: string) => void;
  getCategoryRate: (cat: string) => number;
  taxRates: any;
  taxMethod: string;
  setTaxMethod: (method: string) => void;
  isLoading?: boolean;
  milestones?: any;
  netRates?: any;
  groupedCategories?: Record<string, { key: string; name: string }[]>;
};

export const DashboardView: React.FC<DashboardViewProps> = ({
  transactions,
  businessCategory,
  businessName,
  setViewMode,
  setShowSettingsModal,
  getTaxDeadlineInfo,
  formatVND,
  handleCancelEditTransaction,
  showTaxDetailModal,
  setShowTaxDetailModal,
  handleSignOut,
  showSettingsModal,
  isSavingSettings,
  handleSaveSettings,
  setBusinessName,
  setBusinessCategory,
  declarationType,
  setDeclarationType,
  getCategoryRate,
  taxRates,
  taxMethod,
  setTaxMethod,
  isLoading = false,
  milestones = {
    exemption: 1000000000,
    net_level_1: 3000000000,
    net_level_2: 50000000000
  },
  netRates = {
    level_1: 0.15,
    level_2: 0.17,
    level_3: 0.20
  },
  groupedCategories = {}
}) => {
  const currentMonth = new Date().getMonth() + 1;
  const currentYear = new Date().getFullYear();

  const monthlyTransactions = transactions.filter((t: any) => {
    if (!t.date) return false;
    const [year, month] = t.date.split('-');
    return parseInt(month) === currentMonth && parseInt(year) === currentYear;
  });

  const monthlyRevenue = monthlyTransactions.reduce((sum: number, t: any) => sum + (parseFloat(t.amount || 0) > 0 ? parseFloat(t.amount || 0) : 0), 0);
  const monthlyExpenses = monthlyTransactions.reduce((sum: number, t: any) => sum + (parseFloat(t.amount || 0) < 0 ? Math.abs(parseFloat(t.amount || 0)) : 0), 0);

  const annualTransactions = transactions.filter((t: any) => {
    if (!t.date) return false;
    const [year] = t.date.split('-');
    return parseInt(year) === currentYear;
  });

  const annualRevenue = annualTransactions.reduce((sum: number, t: any) => sum + (parseFloat(t.amount || 0) > 0 ? parseFloat(t.amount || 0) : 0), 0);
  const annualExpenses = annualTransactions.reduce((sum: number, t: any) => sum + (parseFloat(t.amount || 0) < 0 ? Math.abs(parseFloat(t.amount || 0)) : 0), 0);

  const isTaxExempt = annualRevenue <= milestones.exemption;
  const remainingToThreshold = Math.max(0, milestones.exemption - annualRevenue);

  // Quy tắc tự động chuyển đổi khi doanh thu lũy kế năm vượt ngưỡng
  useEffect(() => {
    if (annualRevenue > milestones.net_level_1 && taxMethod !== 'thu_nhap') {
      setTaxMethod('thu_nhap');
    }
  }, [annualRevenue, taxMethod, setTaxMethod, milestones.net_level_1]);

  useEffect(() => {
    if (declarationType === 'quy' || declarationType === 'thang') {
      if (annualRevenue > milestones.net_level_2 && declarationType !== 'thang') {
        setDeclarationType('thang');
      } else if (annualRevenue <= milestones.net_level_2 && declarationType !== 'quy') {
        setDeclarationType('quy');
      }
    }
  }, [annualRevenue, declarationType, setDeclarationType, milestones.net_level_2]);

  const deadlineInfo = getTaxDeadlineInfo();
  const autoSwitchedToMonthly = deadlineInfo?.autoSwitchedToMonthly;
  const autoSwitchedToQuarterly = deadlineInfo?.autoSwitchedToQuarterly;

  const rateInfo = (taxRates && taxRates[businessCategory]) || {
    name: "Hoạt động sản xuất, kinh doanh khác",
    gtgt: 0.02,
    tncn: 0.01,
    total: 0.03
  };
  const gtgtRate = rateInfo.gtgt;
  const tncnRate = rateInfo.tncn;

  // Tính toán số thuế dự kiến trong tháng hiện tại
  let monthlyGtgtTax = 0;
  let monthlyTncnTax = 0;
  let tncnRateUsed = tncnRate;

  if (!isTaxExempt) {
    monthlyGtgtTax = monthlyRevenue * gtgtRate;
    if (taxMethod === 'thu_nhap') {
      const taxableIncome = Math.max(0, monthlyRevenue - monthlyExpenses);
      if (annualRevenue <= milestones.net_level_1) {
        tncnRateUsed = netRates.level_1;
      } else if (annualRevenue <= milestones.net_level_2) {
        tncnRateUsed = netRates.level_2;
      } else {
        tncnRateUsed = netRates.level_3;
      }
      monthlyTncnTax = taxableIncome * tncnRateUsed;
    } else {
      const prevCumulative = Math.max(0, annualRevenue - monthlyRevenue);
      monthlyTncnTax = Math.max(0, annualRevenue - milestones.exemption) * tncnRate - Math.max(0, prevCumulative - milestones.exemption) * tncnRate;
      tncnRateUsed = tncnRate;
    }
  }

  const monthlyTax = monthlyGtgtTax + monthlyTncnTax;

  return (
    <div className="dashboard-layout">
      <div className="dashboard-container">
        {/* Header */}
        <div className="dashboard-header">
          <div>
            <div className="dashboard-greeting">Xin chào, Hộ kinh doanh</div>
            {isLoading ? (
              <div className="skeleton-shimmer" style={{ width: '220px', height: '36px', marginTop: '0.45rem', borderRadius: '8px' }}></div>
            ) : (
              <h2 className="dashboard-title">{businessName}</h2>
            )}
          </div>
          <button className="dashboard-settings-btn" onClick={() => setShowSettingsModal(true)} title="Cài đặt Hộ kinh doanh">
            <i className="fa-solid fa-gear"></i>
          </button>
        </div>

        {/* Hộp thông báo */}
        {isLoading ? (
          <div className="dashboard-alert skeleton-shimmer" style={{ border: '1px solid rgba(226, 232, 240, 0.8)', boxShadow: 'var(--shadow-sm)', minHeight: '62px', marginBottom: '1rem' }}>
            <div className="dashboard-alert-content" style={{ width: '100%' }}>
              <i className="fa-solid fa-spinner fa-spin" style={{ color: '#94a3b8' }}></i>
              <span style={{ display: 'inline-block', width: '220px', height: '14px', backgroundColor: '#cbd5e1', opacity: 0.4, borderRadius: '4px' }}></span>
            </div>
          </div>
        ) : (
          <>
            {autoSwitchedToMonthly && (
              <div className="dashboard-alert" style={{ background: '#fffbeb', borderColor: '#fef3c7', color: '#92400e', boxShadow: 'var(--shadow-sm)', marginBottom: '1rem' }}>
                <div className="dashboard-alert-content">
                  <i className="fa-solid fa-triangle-exclamation" style={{ color: '#d97706', marginRight: '8px' }}></i>
                  <span>Doanh thu lũy kế năm đã vượt {(milestones.net_level_2 / 1000000000).toLocaleString('vi-VN')} tỷ VNĐ. Hệ thống đã tự động chuyển đổi sang kê khai theo Tháng theo quy định pháp luật.</span>
                </div>
              </div>
            )}

            {autoSwitchedToQuarterly && (
              <div className="dashboard-alert" style={{ background: '#fffbeb', borderColor: '#fef3c7', color: '#92400e', boxShadow: 'var(--shadow-sm)', marginBottom: '1rem' }}>
                <div className="dashboard-alert-content">
                  <i className="fa-solid fa-triangle-exclamation" style={{ color: '#d97706', marginRight: '8px' }}></i>
                  <span>Doanh thu lũy kế năm dưới {(milestones.net_level_2 / 1000000000).toLocaleString('vi-VN')} tỷ VNĐ. Hệ thống đã tự động chuyển đổi sang kê khai theo Quý theo quy định pháp luật.</span>
                </div>
              </div>
            )}

            {isTaxExempt ? (
              <div className="dashboard-alert" style={{ background: '#ecfdf5', borderColor: '#a7f3d0', color: '#065f46', boxShadow: 'var(--shadow-sm)' }}>
                <div className="dashboard-alert-content">
                  <i className="fa-solid fa-circle-check" style={{ color: '#10b981' }}></i>
                  <span>Hộ kinh doanh đang được miễn thuế do doanh thu lũy kế năm từ {(milestones.exemption / 1000000000).toLocaleString('vi-VN')} tỷ VNĐ trở xuống.</span>
                </div>
                <span className="dashboard-alert-link" style={{ color: '#059669' }} onClick={() => setShowTaxDetailModal(true)}>Chi tiết →</span>
              </div>
            ) : (
              <div className="dashboard-alert">
                <div className="dashboard-alert-content">
                  <i className="fa-solid fa-bell"></i>
                  <span>{getTaxDeadlineInfo().message}</span>
                </div>
                <span className="dashboard-alert-link" onClick={() => setShowTaxDetailModal(true)}>Chi tiết →</span>
              </div>
            )}
          </>
        )}

        {/* Thẻ thống kê */}
        <div className="dashboard-stats-grid">
          <div className="dashboard-stat-card">
            <span className="stat-card-label">Doanh thu tháng này</span>
            {isLoading ? (
              <div className="skeleton-shimmer" style={{ width: '160px', height: '32px', borderRadius: '6px', margin: '8px 0' }}></div>
            ) : (
              <strong className="stat-card-value value-green">{formatVND(monthlyRevenue)}</strong>
            )}
            <span className="stat-card-sub">
              <i className="fa-solid fa-arrows-rotate"></i> Đồng bộ từ Sổ giao dịch
            </span>
          </div>

          <div className="dashboard-stat-card">
            <span className="stat-card-label">Thuế dự kiến tháng này</span>
            {isLoading ? (
              <div className="skeleton-shimmer" style={{ width: '130px', height: '32px', borderRadius: '6px', margin: '8px 0' }}></div>
            ) : (
              <strong className="stat-card-value value-yellow">{formatVND(monthlyTax)}</strong>
            )}
            <span className="stat-card-sub">
              <i className="fa-solid fa-calculator"></i> Thuế GTGT + TNCN phát sinh
            </span>
          </div>

          <div className="dashboard-stat-card">
            <span className="stat-card-label">Doanh thu lũy kế năm</span>
            {isLoading ? (
              <div className="skeleton-shimmer" style={{ width: '180px', height: '32px', borderRadius: '6px', margin: '8px 0' }}></div>
            ) : (
              <strong className="stat-card-value">{formatVND(annualRevenue)}</strong>
            )}
            {isLoading ? (
              <div className="skeleton-shimmer" style={{ width: '120px', height: '18px', borderRadius: '4px', marginTop: '6px' }}></div>
            ) : (
              <div className="stat-card-sub" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '5px' }}>
                <div>
                  <span className={`stat-badge ${isTaxExempt ? 'badge-green' : 'badge-red'}`}>
                    {isTaxExempt ? `Miễn thuế (<= ${(milestones.exemption / 1000000000).toLocaleString('vi-VN')} tỷ/năm)` : `Đã chịu thuế (> ${(milestones.exemption / 1000000000).toLocaleString('vi-VN')} tỷ/năm)`}
                  </span>
                </div>
                {isTaxExempt ? (
                  <div><i className="fa-solid fa-info-circle"></i> Còn {(remainingToThreshold / 1000000).toFixed(1)} Tr đến ngưỡng chịu thuế</div>
                ) : (
                  <div><i className="fa-solid fa-exclamation-triangle"></i> Đã vượt ngưỡng miễn thuế</div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Tác vụ nhanh */}
        <div className="dashboard-quick-actions">
          <h3>
            <i className="fa-solid fa-circle-play"></i> Tác vụ nhanh
          </h3>
          <div className="quick-actions-btns">
            <button className="action-btn-pill btn-purple-grad" onClick={() => setViewMode('chat')}>
              <i className="fa-regular fa-comments"></i> Chat với AI
            </button>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '-8px', marginLeft: '20px', marginBottom: '8px' }}>
              Giao diện chat + tính thuế nhanh
            </div>

            <button className="action-btn-pill btn-green-grad" onClick={() => { setViewMode('ledger'); handleCancelEditTransaction(); }}>
              <i className="fa-solid fa-book"></i> Sổ giao dịch Thu / Chi
            </button>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '-8px', marginLeft: '20px', marginBottom: '8px' }}>
              Quản lý doanh thu hằng ngày
            </div>

            <button className="action-btn-pill btn-orange-grad" onClick={() => setViewMode('tax_schedule')}>
              <i className="fa-solid fa-calendar-days"></i> Lịch nộp thuế & Trạng thái đóng
            </button>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '-8px', marginLeft: '20px' }}>
              Theo dõi thời hạn và cập nhật lịch đóng thuế GTGT + TNCN định kỳ
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            onClick={handleSignOut}
            style={{ padding: '0.5rem 1rem', background: 'none', border: '1px solid rgb(239, 68, 68)', borderRadius: '8px', color: 'rgb(239, 68, 68)', cursor: 'pointer', fontSize: '0.9rem' }}
          >
            <i className="fa-solid fa-right-from-bracket"></i> <span style={{ textDecoration: 'underline' }}>Đăng xuất tài khoản</span>
          </button>
        </div>
      </div>

      {/* Modal Cài đặt Hộ kinh doanh */}
      {showSettingsModal && (
        <div className="glass-modal-overlay">
          <div className="glass-modal-card" style={{ maxWidth: '650px', overflow: 'hidden' }}>
            <div className="glass-modal-header">
              <h3><i className="fa-solid fa-gear"></i> Cấu hình Hộ kinh doanh</h3>
              <button className="glass-modal-close-btn" onClick={() => setShowSettingsModal(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              <div className="glass-modal-body">
                <div className="dark-form">
                  <div className="dark-form-group">
                    <label>Tên Hộ kinh doanh</label>
                    <input
                      type="text"
                      value={businessName}
                      onChange={(e) => setBusinessName(e.target.value)}
                      required
                      placeholder="Ví dụ: My Business"
                    />
                  </div>
                  <div className="dark-form-group">
                    <label>Ngành nghề kinh doanh</label>
                    <select value={businessCategory} onChange={(e) => setBusinessCategory(e.target.value)}>
                      {Object.keys(taxRates).length === 0 ? (
                        <option value={businessCategory}>Đang tải danh sách ngành nghề...</option>
                      ) : (
                        Object.entries(groupedCategories).map(([groupName, items]) => (
                          <optgroup key={groupName} label={groupName}>
                            {items.map((item) => (
                              <option key={item.key} value={item.key}>
                                {item.name}
                              </option>
                            ))}
                          </optgroup>
                        ))
                      )}
                    </select>
                  </div>
                  <div className="dark-form-group">
                    <label>Phương pháp tính thuế</label>
                    <select
                      value={taxMethod}
                      onChange={(e) => setTaxMethod(e.target.value)}
                      disabled={annualRevenue > milestones.net_level_1}
                    >
                      <option value="doanh_thu">Tính theo Doanh thu</option>
                      <option value="thu_nhap">Tính theo Thu nhập tính thuế</option>
                    </select>
                    {annualRevenue > milestones.net_level_1 && (
                      <span style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: '4px', display: 'block' }}>
                        * Doanh thu năm &gt; {(milestones.net_level_1 / 1000000000).toLocaleString('vi-VN')} tỷ bắt buộc áp dụng phương pháp Tính theo Thu nhập tính thuế.
                      </span>
                    )}
                  </div>
                  <div className="dark-form-group">
                    <label>Hình thức nộp thuế / kê khai</label>
                    <select
                      value={declarationType}
                      onChange={(e) => setDeclarationType(e.target.value)}
                      disabled={annualRevenue > milestones.net_level_2}
                    >
                      <option value="quy" disabled={annualRevenue > milestones.net_level_2}>
                        Kê khai theo Quý (Doanh thu &lt;= {(milestones.net_level_2 / 1000000000).toLocaleString('vi-VN')} tỷ/năm)
                      </option>
                      <option value="thang" disabled={annualRevenue <= milestones.net_level_2}>
                        Kê khai theo Tháng (Doanh thu &gt; {(milestones.net_level_2 / 1000000000).toLocaleString('vi-VN')} tỷ/năm)
                      </option>
                      <option value="lan_phat_sinh" disabled={annualRevenue > milestones.net_level_2}>
                        Nộp thuế theo từng lần phát sinh (Kinh doanh không thường xuyên)
                      </option>
                    </select>
                    {annualRevenue > milestones.net_level_2 ? (
                      <span style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: '4px', display: 'block' }}>
                        * Doanh thu năm &gt; {(milestones.net_level_2 / 1000000000).toLocaleString('vi-VN')} tỷ bắt buộc áp dụng kê khai theo Tháng.
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.75rem', color: '#93c5fd', marginTop: '4px', display: 'block' }}>
                        * Doanh thu năm &lt;= {(milestones.net_level_2 / 1000000000).toLocaleString('vi-VN')} tỷ bắt buộc áp dụng kê khai theo Quý (hoặc theo từng lần phát sinh).
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="glass-modal-footer">
                <button type="button" className="glass-btn-secondary" onClick={() => setShowSettingsModal(false)}>Hủy</button>
                <button type="submit" className="glass-btn-primary" disabled={isSavingSettings}>
                  {isSavingSettings ? <><i className="fa-solid fa-spinner fa-spin"></i> Đang lưu...</> : "Lưu cấu hình"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Chi tiết Thuế */}
      {showTaxDetailModal && (
        <div className="glass-modal-overlay" style={{ zIndex: 2000 }}>
          <div className="glass-modal-card" style={{ maxWidth: '650px', overflow: 'hidden' }}>
            <div className="glass-modal-header">
              <h3><i className="fa-solid fa-calculator"></i> Chi tiết Công thức tính thuế</h3>
              <button className="glass-modal-close-btn" onClick={() => setShowTaxDetailModal(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <div className="glass-modal-body" style={{ color: '#1e293b', padding: '20px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

                {/* Bảng chi tiết công thức */}
                <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ padding: '12px 16px', background: '#f8fafc', fontWeight: '700', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', color: '#334155', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    <span>Chỉ tiêu tính toán</span>
                    <span>Giá trị</span>
                  </div>

                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#475569', fontSize: '0.9rem' }}>Doanh thu tháng này:</span>
                    <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>{formatVND(monthlyRevenue)}</strong>
                  </div>

                  {taxMethod === 'thu_nhap' && (
                    <>
                      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#475569', fontSize: '0.9rem' }}>Chi phí tháng này:</span>
                        <strong style={{ color: '#e11d48', fontSize: '0.95rem' }}>-{formatVND(monthlyExpenses)}</strong>
                      </div>
                      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc' }}>
                        <span style={{ color: '#475569', fontSize: '0.9rem', fontWeight: '500' }}>Thu nhập tính thuế:</span>
                        <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>{formatVND(Math.max(0, monthlyRevenue - monthlyExpenses))}</strong>
                      </div>
                    </>
                  )}

                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#475569', fontSize: '0.9rem' }}>Doanh thu lũy kế năm:</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>{formatVND(annualRevenue)}</strong>
                      <span style={{
                        fontSize: '0.75rem',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        fontWeight: '600',
                        background: isTaxExempt ? '#dcfce7' : '#fee2e2',
                        color: isTaxExempt ? '#15803d' : '#b91c1c'
                      }}>
                        {isTaxExempt ? `Từ ${(milestones.exemption / 1000000000).toLocaleString('vi-VN')} tỷ trở xuống (Miễn thuế)` : `Trên ${(milestones.exemption / 1000000000).toLocaleString('vi-VN')} tỷ (Chịu thuế)`}
                      </span>
                    </div>
                  </div>

                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#475569', fontSize: '0.9rem' }}>Ngành nghề áp dụng:</span>
                    <span style={{ fontSize: '0.85rem', color: '#334155', fontWeight: '600', maxWidth: '60%', textAlign: 'right' }}>
                      {rateInfo.name}
                    </span>
                  </div>

                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ color: '#475569', fontSize: '0.9rem' }}>Phương pháp áp dụng:</span>
                    </div>
                    <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>{taxMethod === 'thu_nhap' ? 'Tính theo Thu nhập tính thuế' : 'Tính theo Doanh thu'}</strong>
                  </div>

                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ color: '#475569', fontSize: '0.9rem' }}>Thuế GTGT phải nộp:</span>
                      <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Tỷ lệ áp dụng: {(gtgtRate * 100).toFixed(1)}% trên Doanh thu</span>
                    </div>
                    <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>{formatVND(monthlyGtgtTax)}</strong>
                  </div>

                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ color: '#475569', fontSize: '0.9rem' }}>Thuế TNCN phải nộp:</span>
                      <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                        {taxMethod === 'thu_nhap'
                          ? `Thuế suất lũy tiến: ${(tncnRateUsed * 100).toFixed(1)}% trên Thu nhập tính thuế`
                          : `Thuế suất: ${(tncnRate * 100).toFixed(1)}% trên Doanh thu vượt ngưỡng`
                        }
                      </span>
                    </div>
                    <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>{formatVND(monthlyTncnTax)}</strong>
                  </div>

                  <div style={{ padding: '14px 16px', background: '#f0fdf4', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #bbf7d0' }}>
                    <strong style={{ fontSize: '1rem', color: '#15803d' }}>Tổng thuế dự kiến:</strong>
                    <strong style={{ fontSize: '1.2rem', color: '#166534' }}>
                      {formatVND(monthlyTax)}
                    </strong>
                  </div>
                </div>


              </div>
            </div>
            <div className="glass-modal-footer">
              <button type="button" className="glass-btn-primary" onClick={() => setShowTaxDetailModal(false)}>Đã hiểu</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
