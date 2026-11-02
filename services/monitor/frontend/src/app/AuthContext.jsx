import { createContext, useCallback, useContext, useState } from "react";

const KEY = "mornitor:user";
const AuthContext = createContext(null);

/** The signed-in identity last returned by POST /api/auth/login ({ userId, name }), remembered across a reload
 * for display only (e.g. "signed in as ..."). It is never the source of truth for whether a session is still
 * valid: the backend's own HttpOnly cookie decides that on every request, and a save the cookie no longer
 * covers still fails with 401 regardless of what this says. */
function read() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function write(user) {
  try {
    if (user) localStorage.setItem(KEY, JSON.stringify(user));
    else localStorage.removeItem(KEY);
  } catch {
    /* no storage available: the name just will not be remembered across a reload */
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(read);
  const signIn = useCallback((u) => {
    setUser(u);
    write(u);
  }, []);
  const signOut = useCallback(() => {
    setUser(null);
    write(null);
  }, []);
  return <AuthContext.Provider value={{ user, signIn, signOut }}>{children}</AuthContext.Provider>;
}

/** { user: { name } | null, signIn(user), signOut() }. Reads no network: AuthProvider only remembers the
 * identity a login response already sent, so using it adds no fetch to any page. */
export function useAuth() {
  return useContext(AuthContext);
}
