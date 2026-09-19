import {
  CognitoUser,
  CognitoUserPool,
  AuthenticationDetails,
  CognitoUserAttribute,
  type CognitoUserSession,
} from "amazon-cognito-identity-js";

const ID_TOKEN_KEY = "terra_id_token";
const REFRESH_TOKEN_KEY = "terra_refresh_token";
const EMAIL_KEY = "terra_email";

function getPool(): CognitoUserPool {
  const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID;
  const clientId = process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID;
  if (!userPoolId || !clientId) {
    throw new Error(
      "Auth is not configured: set NEXT_PUBLIC_COGNITO_USER_POOL_ID and " +
        "NEXT_PUBLIC_COGNITO_APP_CLIENT_ID (see docs/DEPLOYMENT.md §6 for " +
        "where these come from)."
    );
  }
  return new CognitoUserPool({ UserPoolId: userPoolId, ClientId: clientId });
}

function persistSession(email: string, session: CognitoUserSession) {
  if (typeof window === "undefined") return;
  localStorage.setItem(ID_TOKEN_KEY, session.getIdToken().getJwtToken());
  localStorage.setItem(
    REFRESH_TOKEN_KEY,
    session.getRefreshToken().getToken()
  );
  localStorage.setItem(EMAIL_KEY, email);
}

export function getIdToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ID_TOKEN_KEY);
}

export function getStoredEmail(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(EMAIL_KEY);
}

export function isAuthenticated(): boolean {
  return getIdToken() !== null;
}

export function signOut() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ID_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
}

export function signUp(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const attributes = [
      new CognitoUserAttribute({ Name: "email", Value: email }),
    ];
    getPool().signUp(email, password, attributes, [], (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

export function confirmSignUp(email: string, code: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: getPool() });
    user.confirmRegistration(code, true, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

export function signIn(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: getPool() });
    const details = new AuthenticationDetails({
      Username: email,
      Password: password,
    });
    user.authenticateUser(details, {
      onSuccess: (session) => {
        persistSession(email, session);
        resolve();
      },
      onFailure: (err) => reject(err),
    });
  });
}
