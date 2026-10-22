// The part of useTideCloak() (@tidecloak/nextjs 0.14.40) this app uses. Both the real SDK and the
// simulated provider satisfy it, so pages do not care which one is running.
export interface TideLike {
  isInitializing: boolean;
  authenticated: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getValueFromToken: (key: string) => any;
  getValueFromIdToken: (key: string) => any;
  hasRealmRole: (role: string) => boolean;
  doEncrypt: (items: { data: string | Uint8Array; tags: string[] }[]) => Promise<(string | Uint8Array)[]>;
  doDecrypt: (items: { encrypted: string | Uint8Array; tags: string[] }[]) => Promise<(string | Uint8Array)[]>;
  AdminAPI: {
    getRealm: () => string;
    getRole: (name: string) => Promise<any>;
    getUserRoles: (userId: string) => Promise<any>;
    addUserRoles: (userId: string, roles: any[]) => Promise<any>;
    fetch: (endpoint: string, init?: RequestInit) => Promise<any>;
  };
}
