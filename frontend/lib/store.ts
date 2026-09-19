import { create } from "zustand";
import { getStoredEmail, isAuthenticated, signOut as cognitoSignOut } from "./auth";

interface AuthState {
  email: string | null;
  authenticated: boolean;
  hydrate: () => void;
  login: (email: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  email: null,
  authenticated: false,
  hydrate: () =>
    set({ email: getStoredEmail(), authenticated: isAuthenticated() }),
  login: (email: string) => set({ email, authenticated: true }),
  logout: () => {
    cognitoSignOut();
    set({ email: null, authenticated: false });
  },
}));
