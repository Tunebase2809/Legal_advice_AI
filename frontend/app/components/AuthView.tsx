import React, { FormEvent } from 'react';

type AuthViewProps = {
  authView: 'login' | 'signup' | 'forgot_password' | 'reset_password';
  authEmail: string;
  setAuthEmail: (email: string) => void;
  authPassword: string;
  setAuthPassword: (password: string) => void;
  authError: string | null;
  setAuthError: (error: string | null) => void;
  authLoading: boolean;
  setAuthView: (view: 'login' | 'signup' | 'forgot_password' | 'reset_password') => void;
  handleSignUp: (e: FormEvent) => Promise<void>;
  handleSignIn: (e: FormEvent) => Promise<void>;
  handleForgotPassword: (e: FormEvent) => Promise<void>;
  handleResetPassword: (e: FormEvent) => Promise<void>;
};

export const AuthView: React.FC<AuthViewProps> = ({
  authView,
  authEmail,
  setAuthEmail,
  authPassword,
  setAuthPassword,
  authError,
  setAuthError,
  authLoading,
  setAuthView,
  handleSignUp,
  handleSignIn,
  handleForgotPassword,
  handleResetPassword
}) => {
  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>
          <i className="fa-solid fa-robot"></i>{' '}
          {authView === 'signup' && 'Đăng ký tài khoản'}
          {authView === 'login' && 'Đăng nhập hệ thống'}
          {authView === 'forgot_password' && 'Khôi phục mật khẩu'}
          {authView === 'reset_password' && 'Đặt lại mật khẩu mới'}
        </h2>
        <p>
          {authView === 'forgot_password'
            ? 'Nhập email để nhận liên kết khôi phục mật khẩu'
            : authView === 'reset_password'
              ? 'Nhập mật khẩu mới cho tài khoản của bạn'
              : 'Hệ thống AI hỗ trợ tư vấn & tính thuế '}
        </p>

        {authError && (
          <div className="auth-error-alert">
            <i className="fa-solid fa-triangle-exclamation"></i> {authError}
          </div>
        )}

        {authView === 'forgot_password' && (
          <form onSubmit={handleForgotPassword} className="auth-form">
            <div className="form-group">
              <label>Địa chỉ Email</label>
              <input
                type="email"
                placeholder="email@example.com"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="auth-submit-btn" disabled={authLoading}>
              {authLoading ? 'Đang gửi...' : 'Gửi liên kết khôi phục'}
            </button>
            <div className="auth-toggle" style={{ marginTop: '1rem', textAlign: 'center' }}>
              <button type="button" onClick={() => { setAuthView('login'); setAuthError(null); }}>
                Quay lại đăng nhập
              </button>
            </div>
          </form>
        )}

        {authView === 'reset_password' && (
          <form onSubmit={handleResetPassword} className="auth-form">
            <div className="form-group">
              <label>Mật khẩu mới</label>
              <input
                type="password"
                placeholder="Mật khẩu mới (tối thiểu 6 ký tự)"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="auth-submit-btn" disabled={authLoading}>
              {authLoading ? 'Đang lưu...' : 'Đặt lại mật khẩu'}
            </button>
          </form>
        )}

        {(authView === 'login' || authView === 'signup') && (
          <form onSubmit={authView === 'signup' ? handleSignUp : handleSignIn} className="auth-form">
            <div className="form-group">
              <label>Địa chỉ Email</label>
              <input
                type="email"
                placeholder="email@example.com"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Mật khẩu</label>
              <input
                type="password"
                placeholder="••••••••"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="auth-submit-btn" disabled={authLoading}>
              {authLoading ? 'Đang xử lý...' : authView === 'signup' ? 'Đăng ký' : 'Đăng nhập'}
            </button>

            {authView === 'login' && (
              <div style={{ textAlign: 'right', marginTop: '-5px' }}>
                <button
                  type="button"
                  onClick={() => { setAuthView('forgot_password'); setAuthError(null); }}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.8rem', cursor: 'pointer', textDecoration: 'underline' }}
                >
                  Quên mật khẩu?
                </button>
              </div>
            )}
          </form>
        )}

        {(authView === 'login' || authView === 'signup') && (
          <div className="auth-toggle">
            {authView === 'signup' ? (
              <>
                Đã có tài khoản?
                <button type="button" onClick={() => { setAuthView('login'); setAuthError(null); }}>
                  Đăng nhập ngay
                </button>
              </>
            ) : (
              <>
                Chưa có tài khoản?
                <button type="button" onClick={() => { setAuthView('signup'); setAuthError(null); }}>
                  Đăng ký ngay
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
