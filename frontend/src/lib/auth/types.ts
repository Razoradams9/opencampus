/** Mirrors the backend's /api/auth response schemas. */
export type Role = "student" | "faculty" | "college_admin";
export type InstitutionStatus = "active" | "suspended" | "archived";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
}

export interface InstitutionRef {
  id: string;
  slug: string;
  name: string;
  status: InstitutionStatus;
}

export interface ActiveInstitution extends InstitutionRef {
  role: Role;
}

export interface Membership {
  id: string;
  role: Role;
  status: "active" | "suspended";
  institution: InstitutionRef;
}

export interface Me {
  user: AuthUser;
  active_institution: ActiveInstitution | null;
  memberships: Membership[];
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  me: Me;
}

export interface InstitutionPublic {
  slug: string;
  name: string;
  status: InstitutionStatus;
  registration_open: boolean;
}

export interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  /** Optional: without it the account joins the open-registration institution. */
  institution_slug?: string;
}

export const ROLE_LABEL: Record<Role, string> = {
  student: "Student",
  faculty: "Faculty",
  college_admin: "College admin",
};
