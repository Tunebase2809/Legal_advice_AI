import React, { ChangeEvent, FormEvent, useState, useRef, useEffect } from 'react';
import { marked } from 'marked';

type Message = {
  id: string;
  text: string;
  isUser: boolean;
  isTyping?: boolean;
  fileName?: string;
  fileType?: string;
  sources?: string[];
  ragBypassedReason?: string | null;
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

type ChatViewProps = {
  userToken: string | null;
  userEmail: string | null;
  taxRates?: any;
  groupedCategories?: any;
  formatVND?: (amount: number) => string;
  handleNumberChange?: (e: ChangeEvent<HTMLInputElement>, setVal: (val: string) => void, setDisplayVal: (val: string) => void) => void;
  setViewMode: (mode: 'dashboard' | 'chat' | 'ledger' | 'tax_schedule') => void;
  handleSignOut: () => void;
};

const DEFAULT_GREETING: Message = {
  id: "init",
  text: "Xin chào! Tôi là AI Trợ lý Thuế. Hãy cung cấp doanh thu và ngành nghề, hoặc đính kèm ảnh tờ khai/hóa đơn để tôi tư vấn.",
  isUser: false,
};

const SourceDetails = ({ sources, onSourceClick }: { sources: string[], onSourceClick: (title: string) => void }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.75rem',
          fontWeight: '700',
          color: 'var(--primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
          userSelect: 'none'
        }}
      >
        <i className="fa-solid fa-circle-info"></i>
        Nguồn tham chiếu ({sources?.length || 0})
        <i className={`fa-solid fa-chevron-${isOpen ? 'up' : 'down'}`} style={{ fontSize: '0.6rem', marginLeft: 'auto', transition: 'transform 0.3s' }}></i>
      </div>

      {isOpen && (
        <div className="sources-list" style={{
          marginTop: '10px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          animation: 'slideDown 0.2s ease-out forwards'
        }}>
          {sources.map((source: string, idx: number) => (
            <span
              key={idx}
              className="source-badge"
              onClick={(e) => {
                e.stopPropagation();
                onSourceClick(source);
              }}
            >
              {source}
            </span>
          ))}
        </div>
      )}
    </>
  );
};

export const ChatView: React.FC<ChatViewProps> = ({
  userToken,
  userEmail,
  taxRates,
  groupedCategories,
  formatVND,
  handleNumberChange,
  setViewMode,
  handleSignOut
}) => {
  // Chat-specific state variables
  const [messages, setMessages] = useState<Message[]>([DEFAULT_GREETING]);
  const [inputMessage, setInputMessage] = useState("");
  const [revenue, setRevenue] = useState("");
  const [displayRevenue, setDisplayRevenue] = useState("");
  const [method, setMethod] = useState("doanh_thu");
  const [expenses, setExpenses] = useState("");
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  const [displayExpenses, setDisplayExpenses] = useState("");
  const [category, setCategory] = useState("hoat_dong_khac");
  const [taxData, setTaxData] = useState<TaxData | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [chatSessions, setChatSessions] = useState<any[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [showFiles, setShowFiles] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [isFilesLoading, setIsFilesLoading] = useState(false);
  const [fileToDelete, setFileToDelete] = useState<any | null>(null);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<{ title: string, content: string } | null>(null);
  const [isSourceLoading, setIsSourceLoading] = useState(false);
  const [showRevenueWarning, setShowRevenueWarning] = useState(false);

  const handleSourceClick = async (title: string) => {
    setIsSourceLoading(true);
    setSelectedSource({ title, content: "" }); // Open modal in loading state
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const token = typeof window !== 'undefined' ? localStorage.getItem('supabase_token') || "" : "";
      const queryParams = new URLSearchParams({ title });
      if (token) queryParams.append('supabase_token', token);

      const response = await fetch(`${apiUrl}/api/document?${queryParams.toString()}`);
      if (response.ok) {
        const data = await response.json();
        if (data && data.content) {
          setSelectedSource({ title, content: data.content });
        } else {
          setSelectedSource({ title, content: data.error || "Không thể tải nội dung." });
        }
      } else {
        setSelectedSource({ title, content: "Lỗi kết nối máy chủ khi tải tài liệu." });
      }
    } catch (error) {
      console.error("Error fetching document:", error);
      setSelectedSource({ title, content: "Đã có lỗi xảy ra." });
    } finally {
      setIsSourceLoading(false);
    }
  };

  // Refs inside ChatView
  const chatWindowRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fallbacks for optional props
  const [internalTaxRates, setInternalTaxRates] = useState<any>(taxRates || {});
  const [internalGroupedCategories, setInternalGroupedCategories] = useState<any>(groupedCategories || {});

  // Fetch tax rates internally if not provided
  useEffect(() => {
    if (taxRates && Object.keys(taxRates).length > 0) {
      setInternalTaxRates(taxRates);
      if (groupedCategories && Object.keys(groupedCategories).length > 0) {
        setInternalGroupedCategories(groupedCategories);
      }
      return;
    }
    const fetchRates = async () => {
      try {
        const response = await fetch('/api/tax-rates');
        if (response.ok) {
          const data = await response.json();
          if (data && data.rates) {
            setInternalTaxRates(data.rates || {});
            setInternalGroupedCategories(data.grouped_categories || {});
          } else {
            setInternalTaxRates(data || {});
          }
        }
      } catch (err) {
        console.error("Lỗi tải bảng tỷ lệ thuế trong ChatView:", err);
      }
    };
    fetchRates();
  }, [taxRates, groupedCategories]);

  // Fallback formatVND
  const localFormatVND = formatVND || ((amount: number) => {
    return new Intl.NumberFormat("vi-VN", {
      style: "currency",
      currency: "VND",
    }).format(amount);
  });

  // Fallback handleNumberChange
  const localHandleNumberChange = handleNumberChange || ((
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
  });


  // Load chat sessions when mounting
  useEffect(() => {
    if (userToken) {
      loadChatSessions(userToken);
    }
  }, [userToken]);

  // Scroll chat window to bottom when messages change
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages]);

  // Tải danh sách các phiên chat từ backend proxy
  const loadChatSessions = async (token: string) => {
    try {
      const response = await fetch(`/api/sessions?supabase_token=${token}`);
      if (response.ok) {
        const sessions = await response.json();
        if (sessions && sessions.length > 0) {
          setChatSessions(sessions);
          // Tự động load phiên gần nhất
          loadSession(sessions[0].id, token);
        } else {
          setMessages([DEFAULT_GREETING]);
        }
      }
    } catch (err) {
      console.error("Lỗi tải danh sách cuộc trò chuyện:", err);
    }
  };

  // Tải và giải mã nội dung của 1 phiên chat từ backend proxy
  const loadSession = async (sessionId: string, token: string | null = userToken) => {
    if (!token) return;
    setCurrentSessionId(sessionId);
    try {
      const response = await fetch(`/api/sessions/${sessionId}/messages?supabase_token=${token}`);
      if (response.ok) {
        const msgs = await response.json();
        if (msgs && msgs.length > 0) {
          setMessages([
            DEFAULT_GREETING,
            ...msgs.map((m: any) => ({
              id: m.id,
              text: m.content,
              isUser: m.role === 'user',
              fileName: m.file_name,
              fileType: m.file_type,
              sources: m.tax_result_snapshot?.sources || m.sources
            }))
          ]);

          // Bản sao mảng để tránh đảo ngược mảng chính
          const reverseMsgs = [...msgs].reverse();
          const lastBotMsg = reverseMsgs.find((m: any) => {
            if (m.role !== 'assistant' || !m.tax_result_snapshot) return false;
            const snapshot = m.tax_result_snapshot;
            return snapshot.tax_snapshot !== undefined || snapshot.is_taxable !== undefined;
          });
          if (lastBotMsg) {
            const snapshot = lastBotMsg.tax_result_snapshot;
            setTaxData(snapshot.tax_snapshot || snapshot);
          } else {
            setTaxData(null);
          }
        } else {
          setMessages([DEFAULT_GREETING]);
        }
      }
    } catch (err) {
      console.error("Lỗi tải nội dung cuộc trò chuyện:", err);
    }
  };

  const createNewSession = () => {
    setCurrentSessionId(null);
    setMessages([DEFAULT_GREETING]);
    setTaxData(null);
  };

  // Xóa phiên chat thông qua backend proxy
  const confirmDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setSessionToDelete(sessionId);
  };

  const executeDeleteSession = async () => {
    if (!sessionToDelete || !userToken) return;

    try {
      const response = await fetch(`/api/sessions/${sessionToDelete}?supabase_token=${userToken}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        const newSessions = chatSessions.filter(s => s.id !== sessionToDelete);
        setChatSessions(newSessions);

        if (currentSessionId === sessionToDelete) {
          if (newSessions.length > 0) {
            loadSession(newSessions[0].id, userToken);
          } else {
            createNewSession();
          }
        }
      }
    } catch (err) {
      console.error("Lỗi xóa cuộc trò chuyện:", err);
    } finally {
      setSessionToDelete(null);
    }
  };

  const handleSendMessage = async (text: string, forceRevenue = 0, forceCat = "", forceMethod = "", forceExpenses = 0, isTaxForm = false) => {
    if (!text.trim() && !selectedFile && !isTaxForm) return;

    const currentFileName = selectedFile ? selectedFile.name : undefined;
    const currentFileType = selectedFile ? selectedFile.name.split('.').pop()?.toUpperCase() : undefined;

    const userId = Date.now().toString();
    const typingId = "typing-" + (Date.now() + 1);

    const newMessages = [
      ...messages,
      {
        id: userId,
        text,
        isUser: true,
        fileName: currentFileName,
        fileType: currentFileType
      },
      {
        id: typingId,
        text: "Đang suy nghĩ",
        isUser: false,
        isTyping: true
      }
    ];
    setMessages(newMessages);
    setInputMessage("");
    setSelectedFile(null); // Clear file after adding to messages state

    const formData = new FormData();
    formData.append("message", text);
    formData.append("revenue", forceRevenue.toString() || "0");
    formData.append("category", forceCat || "hoat_dong_khac");
    formData.append("method", forceMethod || "doanh_thu");
    formData.append("expenses", forceExpenses.toString() || "0");
    if (isTaxForm) formData.append("is_tax_form", "true");
    if (selectedFile) formData.append("file", selectedFile);
    if (userToken) formData.append("supabase_token", userToken);
    if (currentSessionId) formData.append("session_id", currentSessionId);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      // Cập nhật session_id nếu backend tạo mới
      if (data.session_id && data.session_id !== currentSessionId) {
        setCurrentSessionId(data.session_id);
        // Refresh danh sách bên trái (giả lập)
        if (!chatSessions.find(s => s.id === data.session_id)) {
          const cleanTitle = text.replace(/[#*_`]/g, '').trim();
          setChatSessions([{ id: data.session_id, title: cleanTitle.substring(0, 30) + '...' }, ...chatSessions]);
        }
      }

      if (data.error) {
        const errorText = data.error.includes("Tin nhắn bị từ chối") ? data.error : `Lỗi: ${data.error}`;
        setMessages((prev) => {
          if (prev.some((m) => m.id === typingId)) {
            return prev.map((m) =>
              m.id === typingId
                ? { ...m, text: errorText, isTyping: false, ragBypassedReason: data.rag_bypassed_reason }
                : m
            );
          } else {
            return [
              ...prev,
              { id: Date.now().toString(), text: errorText, isUser: false, ragBypassedReason: data.rag_bypassed_reason },
            ];
          }
        });
      } else {
        setMessages((prev) => {
          if (prev.some((m) => m.id === typingId)) {
            return prev.map((m) => {
              if (m.id === typingId) return { ...m, text: data.text, isTyping: false, sources: data.sources, ragBypassedReason: data.rag_bypassed_reason };
              if (m.id === userId && data.user_message) return { ...m, text: data.user_message };
              return m;
            });
          } else {
            const next = prev.map((m) => (m.id === userId && data.user_message) ? { ...m, text: data.user_message } : m);
            return [
              ...next,
              { id: Date.now().toString(), text: data.text, isUser: false, sources: data.sources, ragBypassedReason: data.rag_bypassed_reason },
            ];
          }
        });

        if (data.tax_table) {
          setTaxData(data.tax_table);
        }

        // Nếu vừa gửi file xong, cập nhật lại danh sách file trong kho lưu trữ
        if (currentFileName) {
          fetchFiles();
        }
      }
    } catch (error) {
      setMessages((prev) => {
        if (prev.some((m) => m.id === typingId)) {
          return prev.map((m) =>
            m.id === typingId
              ? { ...m, text: "Xin lỗi, đã có lỗi kết nối đến máy chủ API.", isTyping: false }
              : m
          );
        } else {
          return [
            ...prev,
            { id: Date.now().toString(), text: "Xin lỗi, đã có lỗi kết nối đến máy chủ API.", isUser: false },
          ];
        }
      });
    }
  };

  const fetchFiles = async () => {
    if (!userToken) return;
    setIsFilesLoading(true);
    try {
      const response = await fetch(`/api/files?supabase_token=${userToken}`);
      const data = await response.json();
      setUploadedFiles(data);
    } catch (error) {
      console.error("Error fetching files:", error);
    } finally {
      setIsFilesLoading(false);
    }
  };

  const handleDownload = (filename: string) => {
    if (!userToken) return;
    window.open(`/api/files/${filename}?supabase_token=${userToken}`, "_blank");
  };

  const handleDeleteFile = async (filename: string) => {
    if (!userToken) return;
    setIsFilesLoading(true);
    try {
      const response = await fetch(`/api/files/${filename}?supabase_token=${userToken}`, {
        method: "DELETE",
      });
      if (response.ok) {
        await fetchFiles();
      }
    } catch (error) {
      console.error("Error deleting file:", error);
    } finally {
      setIsFilesLoading(false);
    }
  };

  const onChatSubmit = (e: FormEvent) => {
    e.preventDefault();
    handleSendMessage(inputMessage);
  };

  const onTaxSubmit = (e: FormEvent) => {
    e.preventDefault();

    if (!revenue || Number(revenue) <= 0) {
      alert("Vui lòng nhập doanh thu lớn hơn 0");
      return;
    }

    const numericRevenue = Number(revenue);
    const NET_LEVEL_1 = 3000000000;

    if (numericRevenue > NET_LEVEL_1 && method === 'doanh_thu') {
      setShowRevenueWarning(true);
      return;
    }

    const methodText = method === 'doanh_thu' ? 'Doanh thu' : 'Thu nhập tính thuế';

    let catText = category;
    if (internalGroupedCategories && Object.keys(internalGroupedCategories).length > 0) {
      for (const group of Object.values(internalGroupedCategories as Record<string, any[]>)) {
        const found = group.find((item: any) => item.key === category);
        if (found) {
          catText = found.name;
          break;
        }
      }
    } else if (internalTaxRates && internalTaxRates[category]) {
      catText = internalTaxRates[category].name || category;
    }

    const msgParts = [
      `**📝 Tính thuế cho tôi theo phương pháp "${methodText}":**`,
      `*   **Doanh thu**: ${localFormatVND(Number(revenue))}`
    ];

    if (method === 'thu_nhap') {
      msgParts.push(`*   **Chi phí hợp lý**: ${localFormatVND(Number(expenses))}`);
    }

    msgParts.push(`*   **Ngành nghề**: ${catText}`);
    msgParts.push(`👉 *Hãy giải thích tóm tắt bảng tính thuế này.*`);

    const msg = msgParts.join('\n');
    handleSendMessage(msg, Number(revenue), category, method, Number(expenses), true);
  };

  const onFastTaxSubmit = async (e: React.FormEvent | React.MouseEvent) => {
    e.preventDefault();

    const form = (e.target as HTMLElement).closest('form');
    if (form && !form.checkValidity()) {
      form.reportValidity();
      return;
    }

    if (!revenue || Number(revenue) <= 0) {
      alert("Vui lòng nhập doanh thu lớn hơn 0");
      return;
    }

    const numericRevenue = Number(revenue);
    const NET_LEVEL_1 = 3000000000;

    if (numericRevenue > NET_LEVEL_1 && method === 'doanh_thu') {
      setShowRevenueWarning(true);
      return;
    }

    const formData = new FormData();
    formData.append("revenue", revenue.toString());
    formData.append("category", category);
    formData.append("method", method);
    formData.append("expenses", expenses.toString() || "0");
    if (userToken) formData.append("supabase_token", userToken);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${apiUrl}/api/calculate-tax`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (data.error) {
        alert(data.error);
      } else if (data.tax_table) {
        setTaxData(data.tax_table);
      }
    } catch (error) {
      console.error("Fast tax calculation failed:", error);
      alert("Đã có lỗi xảy ra khi tính thuế nhanh.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const maxSizeBytes = 2 * 1024 * 1024; // 2MB
      if (file.size > maxSizeBytes) {
        alert("Kích thước tệp tin không được vượt quá 2MB.");
        e.target.value = '';
        return;
      }
      setSelectedFile(file);
    }
    e.target.value = '';
  };

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const renderFormattedText = (text: string) => {
    if (!text) return null;

    let html = text.trim();

    const htmlBlockRegex = /^```html\s*([\s\S]*?)\s*```$/i;
    const genericBlockRegex = /^```(?:xml|html)?\s*([\s\S]*?)\s*```$/i;

    if (htmlBlockRegex.test(html)) {
      html = html.replace(htmlBlockRegex, '$1');
    } else if (genericBlockRegex.test(html)) {
      html = html.replace(genericBlockRegex, '$1');
    }

    html = html.trim();

    try {
      html = marked.parse(html, { breaks: true, gfm: true, async: false }) as string;
    } catch (err) {
      console.error("Lỗi parse markdown bằng marked:", err);
    }

    html = html.replace(/<table([^>]*)>([\s\S]*?)<\/table>/gi, '<div class="table-container"><table$1>$2</table></div>');

    return <div className="formatted-content" dangerouslySetInnerHTML={{ __html: html }} />;
  };

  return (
    <div className="layout" style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', overflow: 'hidden' }}>

      <header className="app-header" style={{ padding: '12px 20px', backgroundColor: '#fff', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', width: '100%', flexShrink: 0 }}>
        <button onClick={() => setViewMode('dashboard')} className="header-back-btn" title="Quay lại Dashboard">
          <i className="fa-solid fa-arrow-left"></i> Quay lại Dashboard
        </button>
        <div className="header-content">
          <h1 style={{ fontSize: '1.2rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', fontWeight: 'bold' }}>
            <i className="fa-solid fa-robot"></i> AI Trợ lý Khai báo Thuế
          </h1>
        </div>
        <button
          className="header-toggle-sidebar-btn"
          onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)}
          title={isRightSidebarOpen ? "Ẩn bảng tính thuế nhanh" : "Hiện bảng tính thuế nhanh"}
        >
          <i className="fa-solid fa-calculator"></i>
          {isRightSidebarOpen ? "Ẩn tính thuế" : "Tính thuế nhanh"}
        </button>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', width: '100%' }}>
        {/* SIDEBAR TƯƠNG TỰ GEMINI */}
        <div className="sidebar" style={{ width: '280px', backgroundColor: '#f0f4f9', padding: '15px', display: 'flex', flexDirection: 'column', borderRight: '1px solid #e0e0e0', overflowY: 'hidden' }}>

          <button className='primary-button'
            onClick={createNewSession}
            style={{ border: 'none', borderRadius: '20px', padding: '15px', display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
            <i className="fa-solid fa-plus"></i> Cuộc trò chuyện mới
          </button>

          <div style={{ marginTop: '20px', flex: 1, overflowY: 'auto' }}>
            <h4 style={{ fontSize: '12px', color: '#666', textTransform: 'uppercase', marginBottom: '10px', marginLeft: '5px' }}>Lịch sử trò chuyện</h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '5px' }}>
              {chatSessions.map((session) => (
                <li key={session.id} style={{ display: 'flex', alignItems: 'center', backgroundColor: currentSessionId === session.id ? '#d3e3fd' : 'transparent', borderRadius: '8px' }}>
                  <button
                    onClick={() => loadSession(session.id)}
                    style={{ flex: 1, textAlign: 'left', padding: '12px 10px', border: 'none', backgroundColor: 'transparent', color: currentSessionId === session.id ? '#041e49' : '#444', cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '13px' }}>
                    <i className="fa-regular fa-message" style={{ marginRight: '8px' }}></i> {session.title.replace(/[#*_`]/g, '').trim()}
                  </button>
                  <button
                    className='user-logout-btn'
                    onClick={(e) => confirmDeleteSession(e, session.id)}
                    title="Xóa cuộc trò chuyện"
                    style={{ backgroundColor: 'transparent' }}>
                    <i className="fa-solid fa-trash-can"></i>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Phần cuối Sidebar: Quản lý tệp & User Profile */}
          <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '10px', borderTop: '1px solid #e0e0e0', paddingTop: '15px' }}>
            <button
              onClick={() => { setShowFiles(true); fetchFiles(); }}
              className="sidebar-action-btn"
            >
              <i className="fa-solid fa-folder-open" style={{ fontSize: '16px', color: '#5f6368' }}></i>
              <span style={{ fontSize: '13px', fontWeight: 500 }}>Quản lý tệp tin</span>
            </button>

            {/* User Profile Card */}
            <div className="user-profile-card">
              {/* Avatar */}
              <div className="user-avatar">
                {userEmail ? userEmail[0] : 'U'}
              </div>

              {/* Email */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="user-email-text" title={userEmail || ""}>
                  {userEmail}
                </div>
              </div>

              {/* Logout button */}
              <button
                onClick={handleSignOut}
                title="Đăng xuất"
                className="user-logout-btn"
              >
                <i className="fa-solid fa-right-from-bracket" style={{ fontSize: '14px' }}></i>
              </button>
            </div>
          </div>
        </div>

        <main className="main-content" style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
          <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
            <div className="chat-section">
              <div className="chat-window" ref={chatWindowRef}>
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`message ${msg.isUser ? "user-message" : "ai-message"}`}
                  >
                    <div className="message-avatar">
                      <i className={`fa-solid ${msg.isUser ? "fa-user" : "fa-robot"}`}></i>
                    </div>
                    <div className="message-bubble">
                      {msg.fileName && (
                        <div className="file-attachment">
                          <div className="file-info-container">
                            <div className="file-icon-box">
                              <i className={`fa-solid ${msg.fileType === 'PDF' ? 'fa-file-pdf' :
                                (['JPG', 'PNG', 'JPEG', 'WEBP'].includes(msg.fileType || '') ? 'fa-file-image' :
                                  (['XLS', 'XLSX', 'CSV'].includes(msg.fileType || '') ? 'fa-file-excel' : 'fa-file-lines'))
                                }`}></i>
                            </div>
                            <div className="file-details">
                              <span className="file-name-text">{msg.fileName}</span>
                              <span className="file-type-badge">{msg.fileType}</span>
                            </div>
                          </div>
                        </div>
                      )}
                      {msg.isTyping ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>{msg.text}</span>
                          <div className="typing-indicator" style={{ transform: 'translateY(2px)' }}>
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                          </div>
                        </div>
                      ) : (
                        <div className="message-content-fade-in">
                          {renderFormattedText(msg.text)}

                          {(msg.sources && msg.sources.length > 0) || msg.ragBypassedReason ? (
                            <div className="sources-wrapper" style={{
                              marginTop: '12px',
                              paddingTop: '12px',
                              borderTop: '1px solid var(--border-color)',
                            }}>
                              {msg.ragBypassedReason ? (
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '8px',
                                  fontSize: '0.75rem',
                                  fontWeight: '700',
                                  color: 'var(--primary)',
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.03em',
                                }}>
                                  <i className="fa-solid fa-circle-info"></i>
                                  Nguồn tham chiếu: 0 ({msg.ragBypassedReason})
                                </div>
                              ) : (
                                <SourceDetails sources={msg.sources || []} onSourceClick={handleSourceClick} />
                              )}
                            </div>
                          ) : null}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="input-area">
                {selectedFile && (
                  <div className="file-preview">
                    <i className="fa-solid fa-file-invoice"></i> Đã đính kèm: {selectedFile.name}
                    <button onClick={() => setSelectedFile(null)}><i className="fa-solid fa-xmark"></i></button>
                  </div>
                )}
                <form onSubmit={onChatSubmit} className="chat-form">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    style={{ display: "none" }}
                    accept=".xlsx,.xls,.csv,.pdf,image/*"
                  />
                  <button type="button" className="icon-button" onClick={handleAttachClick} title="Đính kèm Excel/PDF/Ảnh hóa đơn">
                    <i className="fa-solid fa-paperclip"></i>
                  </button>

                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    placeholder="Nhập câu hỏi hoặc gửi ảnh tờ khai/hóa đơn..."
                    autoComplete="off"
                  />
                  <button type="submit" className="primary-button" disabled={!inputMessage.trim() && !selectedFile}>
                    <i className="fa-solid fa-paper-plane"></i> Gửi
                  </button>
                </form>
              </div>
            </div>

            {isRightSidebarOpen && (
              <div className="side-panel" style={{ transition: 'all 0.3s ease' }}>
                <h3>
                  <i className="fa-solid fa-calculator"></i> Tính thuế nhanh
                </h3>
                <form onSubmit={onTaxSubmit} className="tax-form">
                  <div className="form-group">
                    <label>Phương pháp tính thuế:</label>
                    <select value={method} onChange={(e) => setMethod(e.target.value)}>
                      <option value="doanh_thu">Tính theo Doanh thu</option>
                      <option value="thu_nhap">Tính theo Thu nhập tính thuế (DT - Chi phí)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Doanh thu năm (VNĐ):</label>
                    <input
                      type="text"
                      value={displayRevenue}
                      onChange={(e) => localHandleNumberChange(e, setRevenue, setDisplayRevenue)}
                      onBlur={() => {
                        if (revenue) {
                          setDisplayRevenue(revenue.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + ",00");
                        }
                      }}
                      onFocus={() => {
                        if (revenue) {
                          setDisplayRevenue(revenue.replace(/\B(?=(\d{3})+(?!\d))/g, "."));
                        }
                      }}
                      placeholder="VD: 600.000.000,00"
                      required
                    />
                  </div>
                  {method === "thu_nhap" && (
                    <div className="form-group">
                      <label>Chi phí hợp lý (VNĐ):</label>
                      <input
                        type="text"
                        value={displayExpenses}
                        onChange={(e) => localHandleNumberChange(e, setExpenses, setDisplayExpenses)}
                        onBlur={() => {
                          if (expenses) {
                            setDisplayExpenses(expenses.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + ",00");
                          }
                        }}
                        onFocus={() => {
                          if (expenses) {
                            setDisplayExpenses(expenses.replace(/\B(?=(\d{3})+(?!\d))/g, "."));
                          }
                        }}
                        placeholder="VD: 100.000.000,00"
                        required
                      />
                    </div>
                  )}
                  <div className="form-group">
                    <label>Ngành nghề:</label>
                    <select value={category} onChange={(e) => setCategory(e.target.value)}>
                      {Object.keys(internalTaxRates).length === 0 ? (
                        <option value={category}>Đang tải danh sách ngành nghề...</option>
                      ) : (
                        Object.entries(internalGroupedCategories as Record<string, any[]>).map(([groupName, items]) => (
                          <optgroup key={groupName} label={groupName}>
                            {items.map((item: any) => (
                              <option key={item.key} value={item.key}>
                                {item.name}
                              </option>
                            ))}
                          </optgroup>
                        ))
                      )}
                    </select>
                  </div>
                  <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
                    <button type="submit" className="secondary-button" style={{ flex: 1 }}>
                      <i className="fa-solid fa-robot"></i> AI Tư Vấn
                    </button>
                    <button type="button" onClick={onFastTaxSubmit} className="secondary-button" style={{ flex: 1 }}>
                      <i className="fa-solid fa-bolt"></i> Tính Nhanh
                    </button>
                  </div>
                </form>

                {taxData && (
                  <div className="card result-card" style={{ display: "block", marginTop: "0.5rem" }}>
                    <h3>Kết quả Tính Thuế</h3>
                    <div>
                      {!taxData.is_taxable ? (
                        <>
                          <div className="tax-item">
                            <span>Trạng thái:</span>
                            <strong>Được miễn thuế</strong>
                          </div>
                          <div className="tax-item">
                            <p><strong>Lý do: </strong>{taxData.reason}</p>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="tax-item">
                            <span>Doanh thu:</span>
                            <strong>{localFormatVND(taxData.revenue || 0)}</strong>
                          </div>
                          <div className="tax-item">
                            <span>DT tính thuế GTGT (toàn bộ):</span>
                            <strong>{localFormatVND(taxData.taxable_revenue_gtgt || 0)}</strong>
                          </div>
                          {taxData.taxable_revenue_tncn !== undefined && (
                            <div className="tax-item">
                              <span>DT tính thuế TNCN (vượt 1 tỷ):</span>
                              <strong>{localFormatVND(taxData.taxable_revenue_tncn || 0)}</strong>
                            </div>
                          )}
                          {taxData.taxable_income !== undefined && (
                            <div className="tax-item">
                              <span>Thu nhập tính thuế:</span>
                              <strong>{localFormatVND(taxData.taxable_income || 0)}</strong>
                            </div>
                          )}
                          <div className="tax-item">
                            <span>Thuế GTGT:</span>
                            <span>{localFormatVND(taxData.tax_gtgt || 0)}</span>
                          </div>
                          <div className="tax-item">
                            <span>Thuế TNCN:</span>
                            <span>{localFormatVND(taxData.tax_tncn || 0)}</span>
                          </div>
                          <div className="tax-item tax-total" style={{ alignItems: "center" }}>
                            <span style={{ fontSize: "1.05rem", fontWeight: "bold" }}>Tổng thuế phải nộp:</span>
                            <span style={{ fontSize: "1.05rem", fontWeight: "bold", color: "#15803d" }}>{localFormatVND(taxData.total_tax || 0)}</span>
                          </div>
                          <div style={{
                            marginTop: "15px",
                            padding: "12px",
                            backgroundColor: "#f0fdf4",
                            border: "1px solid #bbf7d0",
                            borderRadius: "8px",
                            fontSize: "0.85rem",
                            color: "#166534",
                            lineHeight: "1.6",
                            whiteSpace: "pre-wrap"
                          }}>
                            <strong><i className="fa-solid fa-circle-info"></i> Giải thích:</strong><br />
                            {taxData.explanation}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}



          </div>
        </main>
      </div>

      {/* Modal quản lý file */}
      {showFiles && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', borderRadius: '12px', width: '90%', maxWidth: '600px', maxHeight: '80vh', display: 'flex', flexDirection: 'column', boxShadow: '0 8px 30px rgba(0,0,0,0.2)' }}>
            <div className="glass-modal-header" style={{ padding: '20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px', fontSize: '1.2rem', color: '#1a1a1a' }}>
                <i className="fa-solid fa-folder-open" style={{ color: '#5f6368' }}></i> Danh sách tệp đã tải lên
              </h3>
              <button className="glass-modal-close-btn" onClick={() => setShowFiles(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '15px', position: 'relative' }}>
              {isFilesLoading && (
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
                  borderRadius: '12px'
                }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                    <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#4f46e5' }}></i>
                    <span style={{ fontSize: '0.9rem', color: '#4f46e5', fontWeight: '600' }}>Đang cập nhật danh sách...</span>
                  </div>
                </div>
              )}
              {uploadedFiles.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: '#888' }}>
                  <i className="fa-solid fa-file-circle-exclamation" style={{ fontSize: '48px', marginBottom: '10px', display: 'block', opacity: 0.5 }}></i>
                  Chưa có tệp tin nào được tải lên.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {uploadedFiles.map((file) => (
                    <div key={file.name} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', borderRadius: '10px', border: '1px solid #eee', backgroundColor: '#fafafa' }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: '#fff', border: '1px solid #eee', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5f6368' }}>
                        <i className={`fa-solid ${file.type === 'PDF' ? 'fa-file-pdf' : (['JPG', 'PNG', 'JPEG', 'WEBP'].includes(file.type) ? 'fa-file-image' : (['XLS', 'XLSX', 'CSV'].includes(file.type) ? 'fa-file-excel' : 'fa-file-lines'))}`} style={{ fontSize: '18px' }}></i>
                      </div>
                      <div style={{ flex: 1, overflow: 'hidden' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: '#333', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.name}</div>
                        <div style={{ fontSize: '12px', color: '#888' }}>{(file.size / 1024).toFixed(1)} KB • {new Date(file.ctime * 1000).toLocaleDateString('vi-VN')}</div>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button onClick={() => handleDownload(file.name)} title="Tải xuống" className='ledger-action-btn btn-edit'>
                          <i className="fa-solid fa-download"></i>
                        </button>
                        <button onClick={() => setFileToDelete(file)} title="Xóa" className='ledger-action-btn btn-delete'>
                          <i className="fa-solid fa-trash-can"></i>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{ padding: '15px', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'center' }}>
              <button onClick={() => setShowFiles(false)} className="primary-button" style={{ padding: '10px 24px', fontSize: '14px' }}>Đóng</button>
            </div>
          </div>
        </div>
      )}
      {/* Modal xác nhận xóa tệp tin */}
      {fileToDelete && (
        <div className="glass-modal-overlay" style={{ zIndex: 1010 }}>
          <div className="glass-modal-card" style={{ maxWidth: '450px' }}>
            <div className="glass-modal-header" style={{ borderBottom: '1px solid #fee2e2' }}>
              <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px' }}><i className="fa-solid fa-triangle-exclamation"></i> Xác nhận xóa tệp tin</h3>
              <button className="glass-modal-close-btn" onClick={() => setFileToDelete(null)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <div className="glass-modal-body" style={{ padding: '20px', color: '#1e293b' }}>
              <p style={{ margin: '0 0 16px 0', fontSize: '0.95rem', fontWeight: '500' }}>Bạn có chắc chắn muốn xóa tệp tin này không? Hành động này không thể hoàn tác.</p>

              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '14px', fontSize: '0.9rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ color: '#64748b' }}>Tên tệp tin:</span>
                  <strong style={{ color: '#334155', wordBreak: 'break-all', marginLeft: '12px', textAlign: 'right' }}>{fileToDelete.name}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ color: '#64748b' }}>Định dạng:</span>
                  <span className="file-type-badge" style={{ margin: 0 }}>{fileToDelete.type}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b' }}>Kích thước:</span>
                  <strong style={{ color: '#334155' }}>{(fileToDelete.size / 1024).toFixed(1)} KB</strong>
                </div>
              </div>
            </div>
            <div className="glass-modal-footer" style={{ justifyContent: 'flex-end', gap: '8px', padding: '12px 20px' }}>
              <button type="button" className="glass-btn-secondary" onClick={() => setFileToDelete(null)}>Hủy</button>
              <button type="button" className="glass-btn-primary delete"
                onClick={async () => {
                  const filename = fileToDelete.name;
                  setFileToDelete(null);
                  await handleDeleteFile(filename);
                }}>
                <i className="fa-solid fa-trash-can"></i> Xóa
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Modal xác nhận xóa cuộc trò chuyện */}
      {sessionToDelete && (
        <div className="glass-modal-overlay" style={{ zIndex: 1010 }}>
          <div className="glass-modal-card" style={{ maxWidth: '450px' }}>
            <div className="glass-modal-header" style={{ borderBottom: '1px solid #fee2e2' }}>
              <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px' }}><i className="fa-solid fa-triangle-exclamation"></i> Xác nhận xóa cuộc trò chuyện</h3>
              <button className="glass-modal-close-btn" onClick={() => setSessionToDelete(null)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <div className="glass-modal-body" style={{ padding: '20px', color: '#1e293b' }}>
              <p style={{ margin: '0 0 16px 0', fontSize: '0.95rem', fontWeight: '500' }}>Bạn có chắc chắn muốn xóa cuộc trò chuyện này không? Hành động này không thể hoàn tác.</p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" className="glass-btn-secondary" onClick={() => setSessionToDelete(null)}>Hủy</button>
                <button type="button" className="glass-btn-primary delete" onClick={executeDeleteSession}>
                  <i className="fa-solid fa-trash-can"></i> Xóa
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal cảnh báo doanh thu > net_level_1 */}
      {showRevenueWarning && (
        <div className="glass-modal-overlay" style={{ zIndex: 1010 }}>
          <div className="glass-modal-card" style={{ maxWidth: '450px' }}>
            <div className="glass-modal-header" style={{ borderBottom: '1px solid #fee2e2' }}>
              <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px' }}><i className="fa-solid fa-triangle-exclamation"></i> Phương pháp không hợp lệ</h3>
              <button className="glass-modal-close-btn" onClick={() => setShowRevenueWarning(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            <div className="glass-modal-body" style={{ padding: '20px', color: '#1e293b' }}>
              <p style={{ margin: '0 0 16px 0', fontSize: '0.95rem', fontWeight: '500' }}>
                Doanh thu của bạn vượt quá 3 tỷ VNĐ. Theo quy định pháp luật, bạn không được phép chọn "Tính theo Doanh thu". Vui lòng chuyển sang phương pháp "Tính theo Thu nhập tính thuế".
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" className="glass-btn-primary" onClick={() => {
                  setMethod('thu_nhap');
                  setShowRevenueWarning(false);
                }}>
                  <i className="fa-solid fa-check"></i> Đổi phương pháp
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal hiển thị nội dung tài liệu */}
      {selectedSource && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }} onClick={() => setSelectedSource(null)}>
          <div style={{ backgroundColor: 'white', borderRadius: '12px', width: '90%', maxWidth: '700px', maxHeight: '80vh', display: 'flex', flexDirection: 'column', boxShadow: '0 8px 30px rgba(0,0,0,0.2)', animation: 'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ padding: '20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '1.1rem', color: '#1a1a1a', fontWeight: 'bold', lineHeight: 1.4 }}>
                <i className="fa-solid fa-file-lines" style={{ color: '#5f6368', marginTop: '3px' }}></i> {selectedSource.title}
              </h3>
              <button className="glass-modal-close-btn" onClick={() => setSelectedSource(null)} style={{ alignSelf: 'flex-start' }}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '20px', position: 'relative', fontSize: '0.95rem', lineHeight: '1.6', color: '#333', whiteSpace: 'pre-wrap' }}>
              {isSourceLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '10px', padding: '40px' }}>
                  <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#4f46e5' }}></i>
                  <span style={{ fontSize: '0.9rem', color: '#4f46e5', fontWeight: '600' }}>Đang tải nội dung văn bản...</span>
                </div>
              ) : (
                selectedSource.content
              )}
            </div>

            <div style={{ padding: '15px', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'center' }}>
              <button onClick={() => setSelectedSource(null)} className="primary-button" style={{ padding: '10px 32px', fontSize: '14px', borderRadius: '24px' }}>Đóng</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
