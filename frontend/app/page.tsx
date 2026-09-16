"use client";

import { useState, useRef, useEffect, FormEvent } from "react";
import { supabase } from '../utils/supabase';
import { AuthView } from "./components/AuthView";
import { ChatView } from "./components/ChatView";

export default function Home() {
  const [userToken, setUserToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  // State xác thực người dùng
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authView, setAuthView] = useState<'login' | 'signup' | 'forgot_password' | 'reset_password'>('login');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);

  const currentUserEmailRef = useRef<string | null>(null);

  // Lắng nghe sự thay đổi trạng thái đăng nhập
  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        const email = session.user.email || null;
        currentUserEmailRef.current = email;
        setUserToken(session.access_token);
        setUserEmail(email);
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
        currentUserEmailRef.current = email;
      } else {
        currentUserEmailRef.current = null;
        setUserToken(null);
        setUserEmail(null);
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

  return (
    <>
      <ChatView
        userToken={userToken}
        userEmail={userEmail}
        handleSignOut={handleSignOut}
      />
      {showSignOutConfirm && (
        <div className="glass-modal-overlay" style={{ zIndex: 3000 }}>
          <div className="glass-modal-card" style={{ maxWidth: '400px', textAlign: 'center', padding: '32px 24px' }}>
            <div style={{ fontSize: '3rem', color: '#ef4444', marginBottom: '16px' }}>
              <i className="fa-solid fa-right-from-bracket"></i>
            </div>
            <h3 style={{ marginBottom: '12px', fontSize: '1.25rem' }}>Xác nhận đăng xuất</h3>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '24px', lineHeight: '1.6' }}>
              Bạn có chắc chắn muốn đăng xuất khỏi tài khoản của mình không?
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
