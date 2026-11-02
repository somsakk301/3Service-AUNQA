import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../../api/authApi";
import { useAuth } from "../../app/AuthContext";
import { useCurriculumCode } from "../../app/curriculumParam";
import { ApiError } from "../../api/client";

const LABEL = { idle: "เข้าสู่ระบบ", saving: "กำลังเข้าสู่ระบบ…" };
const FIELD = "h-12 rounded-lg border border-[#DDE8E2] px-4 text-base text-[#1F2937] focus:border-[#2F7D5B] focus:outline-none focus:ring-2 focus:ring-[#2F7D5B]/30 disabled:opacity-60";

/**
 * Sign-in for recording a Manual Review of a PS the configuration reviews by the user: a username and
 * password, checked by the backend against the Monitor-owned `users` collection (there is no register page —
 * an account exists only if a seed script made it). On success the backend sets the session cookie; this page
 * only remembers the returned display name for the UI (AuthContext), then returns to the PS overview.
 */
export function LoginPage() {
  const { signIn } = useAuth();
  const { search } = useCurriculumCode();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState("idle"); // idle | saving | error

  const onSubmit = async (e) => {
    e.preventDefault();
    setState("saving");
    try {
      const user = await login(username, password);
      signIn(user);
      navigate(`/monitor/ps${search}`, { replace: true });
    } catch (err) {
      setState("error");
      if (!(err instanceof ApiError)) console.error("[Mornitor] login request failed:", err);
    }
  };

  const busy = state === "saving";
  return (
    <div className="mx-auto max-w-sm py-8">
      <p className="text-sm font-semibold uppercase tracking-wide text-[#2F7D5B]">AUN-QA Monitor</p>
      <h1 className="mt-1 text-[28px] font-bold leading-snug text-[#1F2937]">เข้าสู่ระบบ</h1>
      <p className="mt-2 text-base leading-relaxed text-[#667085]">
        สำหรับบันทึกผลตรวจด้วยตนเองของเกณฑ์ที่เปิดให้ผู้ตรวจยืนยันผล
      </p>
      <form className="mt-8 flex flex-col gap-5" onSubmit={onSubmit}>
        <label className="flex flex-col gap-2 text-base font-medium text-[#1F2937]">
          ชื่อผู้ใช้
          <input
            className={FIELD} type="text" autoComplete="username"
            value={username} onChange={(e) => setUsername(e.target.value)} disabled={busy}
            data-testid="login-username" required
          />
        </label>
        <label className="flex flex-col gap-2 text-base font-medium text-[#1F2937]">
          รหัสผ่าน
          <input
            className={FIELD} type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy}
            data-testid="login-password" required
          />
        </label>
        <button
          className="h-12 rounded-lg bg-[#2F7D5B] text-base font-semibold text-white hover:bg-[#205B43] disabled:opacity-60"
          type="submit" disabled={busy} data-testid="login-submit"
        >
          {LABEL[state] ?? LABEL.idle}
        </button>
        {state === "error" && (
          <p className="text-base text-[#C94A4A]" role="alert" data-testid="login-error">
            ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง
          </p>
        )}
      </form>
    </div>
  );
}
