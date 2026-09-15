"use client";

import { useState, useRef, useEffect, FormEvent, ChangeEvent } from "react";
import { supabase } from '../utils/supabase';
import { AuthView } from "./components/AuthView";
import { DashboardView } from "./components/DashboardView";
import { LedgerView } from "./components/LedgerView";
import { TaxScheduleView } from "./components/TaxScheduleView";
import { ChatView } from "./components/ChatView";

type Message = {
  id: string;
  text: string;
  isUser: boolean;
  isTyping?: boolean;
  fileName?: string;
  fileType?: string;
  sources?: string[];
};

type TaxData = {
  is_taxable: boolean;
  reason?: string;
  revenue?: number;
  tax_gtgt?: number;
  tax_tncn?: number;
  total_tax?: number;
  explanation?: string;
  taxable_revenue_gtgt?: number;
  taxable_revenue_tncn?: number;
  taxable_income?: number;
};

export default function Home() {
  const [userToken, setUserToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  // State xác thực người dùng
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authView, setAuthView] = useState<'login' | 'signup' | 'forgot_password' | 'reset_password'>('login');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // States mới cho Dashboard & Sổ thu chi
  const [viewMode, setViewMode] = useState<'dashboard' | 'chat' | 'ledger' | 'tax_schedule'>('dashboard');
  const [businessName, setBusinessName] = useState("My Business");
  const [businessCategory, setBusinessCategory] = useState("ban_buon_ban_le");
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [transactions, setTransactions] = useState<any[]>([]);

  // States cho tính năng Lịch nộp thuế
  const [declarationType, setDeclarationType] = useState<string>("quy");
  const [taxMethod, setTaxMethod] = useState<string>("doanh_thu");
  const [showTaxDetailModal, setShowTaxDetailModal] = useState(false);
  const [taxRates, setTaxRates] = useState<any>({});
  const [groupedCategories, setGroupedCategories] = useState<any>({});
  const [milestones, setMilestones] = useState<any>({
    exemption: 1000000000,
    net_level_1: 3000000000,
    net_level_2: 50000000000
  });
  const [netRates, setNetRates] = useState<any>({
    level_1: 0.15,
    level_2: 0.17,
    level_3: 0.20
  });
  const [taxSchedulePeriods, setTaxSchedulePeriods] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);

  const currentUserEmailRef = useRef<string | null>(null);

  // Helper tính thuế theo tỷ lệ ngành nghề
  const getCategoryRate = (cat: string) => {
    if (taxRates && taxRates[cat]) {
      return taxRates[cat].total;
    }
    return 0.0;
  };

  // Fetch Business Settings từ Backend
  const fetchBusinessSettings = async (token: string) => {
    try {
      const response = await fetch(`/api/business-settings?supabase_token=${token}`);
      if (response.ok) {
        const data = await response.json();
        if (data) {
          setBusinessName(data.business_name || "My Business");
          setBusinessCategory(data.business_category || "ban_buon_ban_le");
          const declType = data.declaration_type || "quy";
          let dType = "quy";
          let tMethod = "doanh_thu";
          
          if (declType.startsWith('lan_phat_sinh_')) {
            dType = 'lan_phat_sinh';
            tMethod = declType.substring('lan_phat_sinh_'.length);
          } else if (declType.startsWith('tung_lan_')) {
            dType = 'lan_phat_sinh';
            tMethod = declType.substring('tung_lan_'.length);
          } else if (declType.startsWith('thang_')) {
            dType = 'thang';
            tMethod = declType.substring('thang_'.length);
          } else if (declType.startsWith('quy_')) {
            dType = 'quy';
            tMethod = declType.substring('quy_'.length);
          } else {
            if (declType === 'lan_phat_sinh' || declType === 'tung_lan' || declType === 'thang' || declType === 'quy') {
              dType = declType === 'tung_lan' ? 'lan_phat_sinh' : declType;
              tMethod = "doanh_thu";
            }
          }
          
          setDeclarationType(dType);
          setTaxMethod(tMethod);
        }
      }
    } catch (err) {
      console.error("Lỗi tải thông tin hộ kinh doanh:", err);
    }
  };

  // Fetch Tax Rates từ Backend
  const fetchTaxRates = async () => {
    try {
      const response = await fetch('/api/tax-rates');
      if (response.ok) {
        const data = await response.json();
        if (data && data.rates) {
          setTaxRates(data.rates || {});
          if (data.grouped_categories) setGroupedCategories(data.grouped_categories);
          if (data.milestones) setMilestones(data.milestones);
          if (data.net_rates) setNetRates(data.net_rates);
        } else {
          setTaxRates(data || {});
        }
      }
    } catch (err) {
      console.error("Lỗi tải bảng tỷ lệ thuế:", err);
    }
  };

  const getTaxDeadlineInfo = () => {
    if (!taxSchedulePeriods || taxSchedulePeriods.length === 0) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const currentYear = today.getFullYear();
      const currentMonth = today.getMonth() + 1;

      let targetQ = 1;
      let dueDateStr = "";
      if (currentMonth <= 3) {
        targetQ = 1;
        dueDateStr = `${currentYear}-04-30`;
      } else if (currentMonth <= 6) {
        targetQ = 2;
        dueDateStr = `${currentYear}-07-31`;
      } else if (currentMonth <= 9) {
        targetQ = 3;
        dueDateStr = `${currentYear}-10-31`;
      } else {
        targetQ = 4;
        dueDateStr = `${currentYear + 1}-01-31`;
      }

      const [year, month, day] = dueDateStr.split('-').map(Number);
      const dueDate = new Date(year, month - 1, day);
      dueDate.setHours(0, 0, 0, 0);

      const diffTime = dueDate.getTime() - today.getTime();
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      const periodLabel = `Quý ${targetQ}/${currentYear}`;
      const message = diffDays < 0
        ? `Đã quá hạn nộp thuế ${periodLabel}! Quá hạn ${Math.abs(diffDays)} ngày.`
        : `Sắp đến thời hạn nộp thuế! Hạn chót nộp thuế ${periodLabel} còn ${diffDays} ngày nữa.`;

      return {
        periodLabel,
        dueDate: dueDateStr,
        days: diffDays,
        message,
        autoSwitchedToMonthly: false,
        autoSwitchedToQuarterly: false
      };
    }

    const unpaidPeriods = taxSchedulePeriods.filter(
      (p: any) => (p.status === 'unpaid' || p.status === 'partial') && (p.estimatedTax || 0) > 0
    );

    let targetPeriod = null;
    if (unpaidPeriods.length > 0) {
      const sortedUnpaid = [...unpaidPeriods].sort((a, b) => a.dueDate.localeCompare(b.dueDate));
      targetPeriod = sortedUnpaid[0];
    } else {
      const sortedAll = [...taxSchedulePeriods].sort((a, b) => b.dueDate.localeCompare(a.dueDate));
      targetPeriod = sortedAll[0];
    }

    if (targetPeriod) {
      const dueDateStr = targetPeriod.dueDate;
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const [year, month, day] = dueDateStr.split('-').map(Number);
      const dueDate = new Date(year, month - 1, day);
      dueDate.setHours(0, 0, 0, 0);

      const diffTime = dueDate.getTime() - today.getTime();
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

      const periodLabel = targetPeriod.periodLabel;
      let message = "";
      if (diffDays < 0) {
        message = `Đã quá hạn nộp thuế ${periodLabel}! Quá hạn ${Math.abs(diffDays)} ngày.`;
      } else {
        message = `Sắp đến thời hạn nộp thuế! Hạn chót nộp thuế ${periodLabel} còn ${diffDays} ngày nữa.`;
      }

      return {
        periodLabel,
        dueDate: dueDateStr,
        days: diffDays,
        message,
        autoSwitchedToMonthly: targetPeriod.autoSwitchedToMonthly || false,
        autoSwitchedToQuarterly: targetPeriod.autoSwitchedToQuarterly || false
      };
    }

    return { periodLabel: "", dueDate: "", days: 0, message: "", autoSwitchedToMonthly: false, autoSwitchedToQuarterly: false };
  };

  const fetchTaxSchedulePeriods = async (token: string) => {
    try {
      const response = await fetch(`/api/tax-schedule-periods?supabase_token=${token}`);
      if (response.ok) {
        const data = await response.json();
        setTaxSchedulePeriods(data);
      }
    } catch (err) {
      console.error("Lỗi tải lịch nộp thuế:", err);
    }
  };

  useEffect(() => {
    if (userToken) {
      fetchTaxSchedulePeriods(userToken);
    }
  }, [userToken, transactions, declarationType]);

  // Format ngày DD/MM/YYYY để hiển thị
  const formatDateDisplay = (dateStr: string) => {
    if (!dateStr) return "";
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  };

  // Moved payment modal handlers to TaxScheduleView

  // Fetch Transactions từ Backend
  const fetchTransactions = async (token: string) => {
    try {
      const response = await fetch(`/api/transactions?supabase_token=${token}`);
      if (response.ok) {
        const data = await response.json();

        // Nếu là tài khoản mới hoàn toàn (chưa có giao dịch nào), tự động tạo 1 giao dịch mặc định 500K để hiển thị giống mockup
        if (data && data.length === 0) {
          const createResp = await fetch('/api/transactions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              supabase_token: token,
              date: new Date().toISOString().split('T')[0],
              amount: 500000,
              description: "Doanh thu bán lẻ tạp hóa đầu ca"
            })
          });
          if (createResp.ok) {
            const refetchResp = await fetch(`/api/transactions?supabase_token=${token}`);
            if (refetchResp.ok) {
              const refetchData = await refetchResp.json();
              setTransactions(refetchData || []);
              return;
            }
          }
        }
        setTransactions(data || []);
      }
    } catch (err) {
      console.error("Lỗi tải danh sách giao dịch:", err);
    }
  };

  // Lắng nghe sự thay đổi trạng thái đăng nhập
  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        const email = session.user.email || null;
        currentUserEmailRef.current = email;
        setUserToken(session.access_token);
        setUserEmail(email);

        setIsLoading(true);
        try {
          await Promise.all([
            fetchBusinessSettings(session.access_token),
            fetchTransactions(session.access_token),
            fetchTaxSchedulePeriods(session.access_token),
            fetchTaxRates()
          ]);
        } catch (e) {
          console.error("Lỗi khi tải dữ liệu khởi tạo:", e);
        } finally {
          setIsLoading(false);
        }
      } else {
        setIsLoading(false);
      }
    };
    checkAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      const email = session?.user?.email || null;
      if (event === 'PASSWORD_RECOVERY') {
        setAuthView('reset_password');
        setUserToken(session?.access_token || null);
        setUserEmail(email);
      } else if (session) {
        setUserToken(session.access_token);
        setUserEmail(email);
        if (currentUserEmailRef.current !== email) {
          currentUserEmailRef.current = email;
          setIsLoading(true);
          try {
            await Promise.all([
              fetchBusinessSettings(session.access_token),
              fetchTransactions(session.access_token),
              fetchTaxSchedulePeriods(session.access_token),
              fetchTaxRates()
            ]);
          } catch (e) {
            console.error("Lỗi tải dữ liệu sau thay đổi phiên đăng nhập:", e);
          } finally {
            setIsLoading(false);
          }
        }
      } else {
        currentUserEmailRef.current = null;
        setUserToken(null);
        setUserEmail(null);
        setTransactions([]);
        setViewMode('dashboard');
        setIsLoading(false);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);


  // Các hàm xác thực bằng email/password qua Supabase Auth
  const handleSignUp = async (e: FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const { data, error } = await supabase.auth.signUp({
        email: authEmail,
        password: authPassword,
        options: {
          emailRedirectTo: window.location.origin
        }
      });
      if (error) throw error;
      alert("Đăng ký thành công! Vui lòng đăng nhập hoặc kiểm tra email xác nhận nếu có.");
      setAuthView('login');
    } catch (err: any) {
      setAuthError(err.message || "Lỗi đăng ký");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignIn = async (e: FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: authEmail,
        password: authPassword
      });
      if (error) throw error;
    } catch (err: any) {
      setAuthError(err.message || "Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản/mật khẩu.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleForgotPassword = async (e: FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(authEmail, {
        redirectTo: window.location.origin
      });
      if (error) throw error;
      alert("Yêu cầu đã gửi! Vui lòng kiểm tra hòm thư Email để nhận liên kết đặt lại mật khẩu.");
      setAuthView('login');
    } catch (err: any) {
      setAuthError(err.message || "Lỗi gửi yêu cầu khôi phục mật khẩu");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleResetPassword = async (e: FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const { error } = await supabase.auth.updateUser({
        password: authPassword
      });
      if (error) throw error;
      alert("Đặt lại mật khẩu thành công! Bạn có thể sử dụng mật khẩu mới để đăng nhập.");
      await supabase.auth.signOut();
      setAuthView('login');
    } catch (err: any) {
      setAuthError(err.message || "Lỗi đặt lại mật khẩu");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignOut = () => {
    setShowSignOutConfirm(true);
  };

  const handleSignOutConfirm = async () => {
    setShowSignOutConfirm(false);
    await supabase.auth.signOut();
  };

  const formatVND = (amount: number) => {
    return new Intl.NumberFormat("vi-VN", {
      style: "currency",
      currency: "VND",
    }).format(amount);
  };

  const handleNumberChange = (
    e: ChangeEvent<HTMLInputElement>,
    setVal: (val: string) => void,
    setDisplayVal: (val: string) => void
  ) => {
    const input = e.target;
    const oldVal = input.value;
    const selectionStart = input.selectionStart || 0;

    // Đếm số lượng chữ số đứng trước vị trí con trỏ trong chuỗi nhập vào
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

    // Phục hồi vị trí con trỏ sau khi React cập nhật DOM
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

  const handleSaveSettings = async (e: FormEvent) => {
    setIsSavingSettings(true);
    e.preventDefault();
    if (!userToken) {
      setIsSavingSettings(false);
      return;
    }
    try {
      const response = await fetch('/api/business-settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          supabase_token: userToken,
          business_name: businessName,
          business_category: businessCategory,
          declaration_type: `${declarationType}_${taxMethod}`
        })
      });
      if (response.ok) {
        setShowSettingsModal(false);
        // Tải lại cấu hình hộ kinh doanh và lịch nộp thuế để cập nhật giao diện ngay lập tức
        fetchBusinessSettings(userToken);
        fetchTaxSchedulePeriods(userToken);
      } else {
        alert("Lỗi khi lưu cài đặt.");
      }
    } catch (err) {
      console.error(err);
      alert("Lỗi kết nối.");
    } finally {
      setIsSavingSettings(false);
    }
  };



  if (!userToken || authView === 'reset_password') {
    return (
      <AuthView
        authView={authView}
        authEmail={authEmail}
        setAuthEmail={setAuthEmail}
        authPassword={authPassword}
        setAuthPassword={setAuthPassword}
        authError={authError}
        setAuthError={setAuthError}
        authLoading={authLoading}
        setAuthView={setAuthView}
        handleSignUp={handleSignUp}
        handleSignIn={handleSignIn}
        handleForgotPassword={handleForgotPassword}
        handleResetPassword={handleResetPassword}
      />
    );
  }

  const renderActiveView = () => {
    if (viewMode === 'dashboard') {
      return (
        <DashboardView
          transactions={transactions}
          businessCategory={businessCategory}
          businessName={businessName}
          setViewMode={setViewMode}
          setShowSettingsModal={setShowSettingsModal}
          getTaxDeadlineInfo={getTaxDeadlineInfo}
          formatVND={formatVND}
          handleCancelEditTransaction={() => { }}
          showTaxDetailModal={showTaxDetailModal}
          setShowTaxDetailModal={setShowTaxDetailModal}
          handleSignOut={handleSignOut}
          showSettingsModal={showSettingsModal}
          isSavingSettings={isSavingSettings}
          handleSaveSettings={handleSaveSettings}
          setBusinessName={setBusinessName}
          setBusinessCategory={setBusinessCategory}
          declarationType={declarationType}
          setDeclarationType={setDeclarationType}
          getCategoryRate={getCategoryRate}
          taxRates={taxRates}
          taxMethod={taxMethod}
          setTaxMethod={setTaxMethod}
          isLoading={isLoading}
          milestones={milestones}
          netRates={netRates}
          groupedCategories={groupedCategories}
        />
      );
    }

    if (viewMode === 'ledger') {
      return (
        <LedgerView
          transactions={transactions}
          userToken={userToken}
          setViewMode={setViewMode}
          fetchTransactions={fetchTransactions}
          formatVND={formatVND}
        />
      );
    }

    if (viewMode === 'tax_schedule') {
      return (
        <TaxScheduleView
          transactions={transactions}
          declarationType={declarationType}
          userToken={userToken}
          setViewMode={setViewMode}
          setShowSettingsModal={setShowSettingsModal}
          fetchTaxSchedulePeriods={fetchTaxSchedulePeriods}
          getTaxSchedulePeriods={() => taxSchedulePeriods}
          formatVND={formatVND}
          formatDateDisplay={formatDateDisplay}
        />
      );
    }

    return (
      <ChatView
        userToken={userToken}
        userEmail={userEmail}
        taxRates={taxRates}
        groupedCategories={groupedCategories}
        formatVND={formatVND}
        handleNumberChange={handleNumberChange}
        setViewMode={setViewMode}
        handleSignOut={handleSignOut}
      />
    );
  };

  return (
    <>
      {renderActiveView()}
      {showSignOutConfirm && (
        <div className="glass-modal-overlay" style={{ zIndex: 3000 }}>
          <div className="glass-modal-card" style={{ maxWidth: '400px', textAlign: 'center', padding: '32px 24px' }}>
            <div style={{ fontSize: '3rem', color: '#ef4444', marginBottom: '16px' }}>
              <i className="fa-solid fa-right-from-bracket"></i>
            </div>
            <h3 style={{ marginBottom: '12px', fontSize: '1.25rem' }}>Xác nhận đăng xuất</h3>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '24px', lineHeight: '1.6' }}>
              Bạn có chắc chắn muốn đăng xuất khỏi tài khoản Hộ kinh doanh của mình không?
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '12px' }}>
              <button type="button" className="glass-btn-secondary" onClick={() => setShowSignOutConfirm(false)}>
                Hủy
              </button>
              <button type="button" className="glass-btn-primary delete" onClick={handleSignOutConfirm}>
                Đăng xuất
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
