import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "bootstrap/dist/css/bootstrap.min.css";
import "./styles.css";
import {
  AlertTriangle, Banknote, BarChart3, Bot, ClipboardCheck, FileDown, Globe2,
  Languages, LayoutDashboard, MessageSquareWarning, ShieldCheck, UserCog, Users,
} from "lucide-react";
import { api, PlatformUser } from "./api";

type Role = "ADMIN" | "FIELD_OFFICER" | "FINANCE" | "REVIEWER" | "SUPPORT" | "MANAGER" | "AUDITOR";
type Route = "dashboard" | "programs" | "intake" | "eligibility" | "payments" | "pdm" | "complaints" | "budgets" | "audit" | "automation" | "users";

const demoUsers: PlatformUser[] = [
  { id: "1", email: "admin@demo.org", full_name: "Platform Administrator", role: "ADMIN", is_active: true },
  { id: "2", email: "field@demo.org", full_name: "Field Officer", role: "FIELD_OFFICER", is_active: true },
  { id: "3", email: "finance@demo.org", full_name: "Finance Officer", role: "FINANCE", is_active: true },
];
const programs = [
  { name: "Sudan Cash Assistance 2026", country: "Sudan", code: "SD", currency: "SDG", reporting: "USD", status: "ACTIVE", approvals: 412 },
  { name: "Kassala Winter Support", country: "Sudan", code: "SD", currency: "USD", reporting: "USD", status: "DRAFT", approvals: 74 },
  { name: "Cross-border Food Voucher", country: "Chad", code: "TD", currency: "XAF", reporting: "USD", status: "PAUSED", approvals: 156 },
];
const beneficiaries = [
  { number: "B-0001", name: "Fatima Osman", household: "HH-101", location: "Kassala", status: "ACTIVE", verification: "VERIFIED" },
  { number: "B-0002", name: "Omer Mohamed", household: "HH-102", location: "Gedaref", status: "REGISTERED", verification: "PENDING" },
  { number: "B-0003", name: "Aisha Ali", household: "HH-103", location: "Port Sudan", status: "ACTIVE", verification: "VERIFIED" },
];
const payments = [
  { id: "PAY-001", beneficiary: "B-0001", amount: "120,000 SDG", channel: "Mobile money", status: "SUCCESS" },
  { id: "PAY-002", beneficiary: "B-0002", amount: "120,000 SDG", channel: "Bank", status: "FAILED" },
  { id: "PAY-003", beneficiary: "B-0003", amount: "120,000 SDG", channel: "Cash", status: "SUBMITTED" },
];
const labels = {
  en: { dashboard: "Dashboard", programs: "Programs", intake: "Intake", eligibility: "Eligibility", payments: "Payments", pdm: "PDM", complaints: "Complaints", budgets: "Budgets", audit: "Audit", automation: "AI & Automation", users: "User Administration", command: "Operations Command Dashboard", signIn: "Sign in", signOut: "Sign out", addUser: "Add user", disabled: "Execution disabled" },
  ar: { dashboard: "لوحة التحكم", programs: "البرامج", intake: "التسجيل", eligibility: "الأهلية", payments: "المدفوعات", pdm: "متابعة ما بعد التوزيع", complaints: "الشكاوى", budgets: "الميزانيات", audit: "سجل التدقيق", automation: "الذكاء والأتمتة", users: "إدارة المستخدمين", command: "لوحة العمليات", signIn: "تسجيل الدخول", signOut: "تسجيل الخروج", addUser: "إضافة مستخدم", disabled: "التنفيذ مغلق" },
};
const routeRoles: Record<Route, Role[]> = {
  dashboard: ["ADMIN", "FIELD_OFFICER", "FINANCE", "REVIEWER", "SUPPORT", "MANAGER", "AUDITOR"],
  programs: ["ADMIN", "MANAGER"], intake: ["ADMIN", "FIELD_OFFICER", "MANAGER"], eligibility: ["ADMIN", "REVIEWER", "MANAGER"], payments: ["ADMIN", "FINANCE", "MANAGER"], pdm: ["ADMIN", "FIELD_OFFICER", "MANAGER"], complaints: ["ADMIN", "SUPPORT", "MANAGER"], budgets: ["ADMIN", "FINANCE", "MANAGER"], audit: ["ADMIN", "MANAGER", "AUDITOR"], automation: ["ADMIN", "MANAGER", "REVIEWER"], users: ["ADMIN"],
};
const nav: Array<[Route, React.ElementType]> = [["dashboard", LayoutDashboard], ["programs", Globe2], ["intake", Users], ["eligibility", ClipboardCheck], ["payments", Banknote], ["pdm", BarChart3], ["complaints", MessageSquareWarning], ["budgets", Banknote], ["audit", ShieldCheck], ["automation", Bot], ["users", UserCog]];

function Badge({ value }: { value: string }) {
  const tone = /FAILED|HIGH|CRITICAL/.test(value) ? "danger" : /PENDING|SUBMITTED|DRAFT|OPEN/.test(value) ? "warning" : /ACTIVE|SUCCESS|VERIFIED|RESOLVED/.test(value) ? "success" : "secondary";
  return <span className={`badge text-bg-${tone}`}>{value}</span>;
}
function DataTable({ title, headings, rows }: { title: string; headings: string[]; rows: React.ReactNode[][] }) {
  return <section className="panel"><div className="panel-title"><h2>{title}</h2><span>tenant isolated</span></div><div className="table-responsive"><table className="table align-middle"><thead><tr>{headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div></section>;
}
function Login({ onLoggedIn }: { onLoggedIn: (user: PlatformUser) => void }) {
  const [error, setError] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const form = new FormData(event.currentTarget); try { onLoggedIn(await api.login(String(form.get("email")), String(form.get("password")))); } catch (reason) { setError(reason instanceof Error ? reason.message : "Login failed"); } };
  return <main className="login-page"><form className="login-card" onSubmit={submit}><div className="brand">H-CAP</div><h1>Platform sign in</h1><p>Use an administrator account created in Django.</p>{error && <div className="alert alert-danger">{error}</div>}<input className="form-control" name="email" type="email" placeholder="email@organization.org" required /><input className="form-control" name="password" type="password" placeholder="Password" required /><button className="btn btn-primary w-100" type="submit">Sign in</button><small>Backend must be running at port 8000.</small></form></main>;
}
function App() {
  const [locale, setLocale] = useState<"en" | "ar">("en");
  const [route, setRoute] = useState<Route>(() => (location.hash.slice(1) as Route) || "dashboard");
  const [currentUser, setCurrentUser] = useState<PlatformUser | null>(null);
  const [testRole, setTestRole] = useState<Role>("ADMIN");
  const [users, setUsers] = useState<PlatformUser[]>(demoUsers);
  const [notice, setNotice] = useState("");
  const t = labels[locale];
  const effectiveRole = (currentUser?.role ?? testRole) as Role;
  useEffect(() => { const update = () => setRoute((location.hash.slice(1) as Route) || "dashboard"); addEventListener("hashchange", update); return () => removeEventListener("hashchange", update); }, []);
  useEffect(() => { if (localStorage.getItem("hcap_token")) api.me().then(setCurrentUser).catch(api.clearToken); }, []);
  const go = (next: Route) => { location.hash = next; };
  const accessible = routeRoles[route]?.includes(effectiveRole);
  const kpis = useMemo(() => [{ label: "Beneficiaries", value: "1,248", icon: Users, tone: "primary" }, { label: "Approvals", value: "932", icon: ClipboardCheck, tone: "success" }, { label: "Paid", value: "784", icon: Banknote, tone: "success" }, { label: "Pending", value: "96", icon: AlertTriangle, tone: "warning" }, { label: "Failed", value: "18", icon: MessageSquareWarning, tone: "danger" }, { label: "Distributed", value: "2.4M SDG", icon: BarChart3, tone: "primary" }], []);
  const loadUsers = async () => { try { const result = await api.users(); setUsers(Array.isArray(result) ? result : result.results); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not load users"); } };
  const addUser = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const form = new FormData(event.currentTarget); const payload = { email: String(form.get("email")), full_name: String(form.get("full_name")), role: String(form.get("role")) as Role, password: String(form.get("password")) }; try { const user = await api.createUser(payload); setUsers((existing) => [...existing, user]); event.currentTarget.reset(); setNotice("User created successfully."); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not create user"); } };
  if (location.hash === "#login") return <Login onLoggedIn={(user) => { setCurrentUser(user); go("dashboard"); }} />;
  const content = !accessible ? <section className="panel"><h2>Access restricted</h2><p>Your selected role does not have permission for this route.</p></section> : route === "dashboard" ? <><section className="kpi-grid">{kpis.map((item) => <article className="kpi" key={item.label}><item.icon className={`text-${item.tone}`} size={22} /><strong>{item.value}</strong><span>{item.label}</span></article>)}</section><section className="row g-3"><div className="col-xl-8"><DataTable title="Programs and geography" headings={["Program", "Country", "Currency", "Status", "Approvals"]} rows={programs.map((program) => [program.name, program.country, program.currency, <Badge value={program.status} />, program.approvals])} /></div><div className="col-xl-4"><section className="panel h-100"><div className="panel-title"><h2>Reconciliation</h2><span>18 exceptions</span></div>{[["Approved amount", "3.1M SDG"], ["Distributed amount", "2.4M SDG"], ["Pending amount", "420K SDG"]].map(([label, value]) => <div className="recon-row" key={label}><span>{label}</span><strong>{value}</strong></div>)}<div className="progress mt-3"><div className="progress-bar" style={{ width: "77%" }}>77%</div></div></section></div></section></> : route === "programs" ? <DataTable title="Multi-country programs" headings={["Program", "Country", "Code", "Program currency", "Reporting currency", "Status"]} rows={programs.map((program) => [program.name, program.country, program.code, program.currency, program.reporting, <Badge value={program.status} />])} /> : route === "intake" ? <DataTable title="Beneficiary intake" headings={["Number", "Name", "Household", "Location", "Status", "Verification"]} rows={beneficiaries.map((person) => [person.number, person.name, person.household, person.location, <Badge value={person.status} />, <Badge value={person.verification} />])} /> : route === "eligibility" ? <DataTable title="Eligibility and approvals" headings={["Beneficiary", "Eligibility", "Approval", "Human reviewer"]} rows={beneficiaries.map((person, index) => [person.number, <Badge value={index === 1 ? "PENDING" : "ELIGIBLE"} />, <Badge value={index === 1 ? "PENDING" : "APPROVED"} />, "Assigned reviewer"])} /> : route === "payments" ? <DataTable title="Fake payment adapter and batches" headings={["Instruction", "Beneficiary", "Amount", "Channel", "Status"]} rows={payments.map((payment) => [payment.id, payment.beneficiary, payment.amount, payment.channel, <Badge value={payment.status} />])} /> : route === "pdm" ? <DataTable title="Post-distribution monitoring" headings={["Location", "Received rate", "Access problems", "Complaint rate", "Satisfaction"]} rows={[["Kassala", "93%", "7%", "3%", "4.5 / 5"], ["Gedaref", "89%", "11%", "5%", "4.2 / 5"]]} /> : route === "complaints" ? <DataTable title="Complaints and operational exceptions" headings={["Case", "Issue", "Severity", "Status"]} rows={[["C-004", "Payment not received", <Badge value="HIGH" />, <Badge value="OPEN" />], ["C-005", "Access problem", <Badge value="MEDIUM" />, <Badge value="IN_PROGRESS" />]]} /> : route === "budgets" ? <DataTable title="Budgets and reporting currency" headings={["Program", "Planned", "Actual", "Reporting currency", "Status"]} rows={programs.map((program) => [program.name, "3.1M", "2.4M", program.reporting, <Badge value="ACTIVE" />])} /> : route === "audit" ? <DataTable title="Traceable audit history" headings={["Time", "Actor", "Action", "Entity", "Correlation"]} rows={[["2026-09-23", "Administrator", "PAYMENT_SIMULATED", "PAY-002", "AUD-101"], ["2026-09-23", "Field officer", "OFFLINE_REGISTRATION_SYNCED", "HH-101", "AUD-102"]]} /> : route === "automation" ? <section className="panel"><div className="panel-title"><h2>AI signals and automation foundation</h2><Badge value="EXECUTION DISABLED" /></div><p>Signal, review queue, rule, and execution-tracking tables are prepared. The backend AI and automation endpoints deliberately return <code>403</code> until you enable your own implementation. AI can only advise; human review remains required.</p><DataTable title="Configured but inactive flows" headings={["Event", "Rule", "Action", "State"]} rows={[["PAYMENT_FAILED", "Retry policy", "Create review task", <Badge value="DISABLED" />], ["DUPLICATE_FLAG", "Duplicate review", "Assign reviewer", <Badge value="DISABLED" />], ["HIGH_SEVERITY_COMPLAINT", "Escalation", "Notify manager", <Badge value="DISABLED" />]]} /></section> : <section className="panel"><div className="panel-title"><h2>User administration</h2><button className="btn btn-outline-primary btn-sm" onClick={loadUsers}>Refresh from API</button></div>{notice && <div className="alert alert-info">{notice}</div>}<div className="row g-3"><div className="col-lg-7"><DataTable title="Tenant users" headings={["Name", "Email", "Role", "Active"]} rows={users.map((user) => [user.full_name, user.email, user.role, <Badge value={user.is_active ? "ACTIVE" : "INACTIVE"} />])} /></div><div className="col-lg-5"><form className="panel" onSubmit={addUser}><h2 className="mb-3">{t.addUser}</h2><input className="form-control mb-2" name="full_name" placeholder="Full name" required /><input className="form-control mb-2" name="email" type="email" placeholder="Email" required /><select className="form-select mb-2" name="role">{Object.keys(routeRoles).length && (["FIELD_OFFICER", "FINANCE", "REVIEWER", "SUPPORT", "MANAGER", "AUDITOR", "ADMIN"] as Role[]).map((role) => <option key={role}>{role}</option>)}</select><input className="form-control mb-3" name="password" type="password" placeholder="Temporary password" minLength={8} required /><button className="btn btn-primary" type="submit">{t.addUser}</button><p className="small text-muted mt-3 mb-0">Admin-only API. Each user inherits the administrator’s tenant.</p></form></div></div></section>;
  const openLogin = () => {
    if (currentUser) {
      api.clearToken();
      setCurrentUser(null);
      setNotice("Signed out. Demo role testing is available.");
      return;
    }
    location.hash = "#login";
  };
  return <div dir={locale === "ar" ? "rtl" : "ltr"}><aside className="sidebar"><div className="brand">H-CAP</div>{nav.map(([item, Icon]) => <button className={`nav-item ${route === item ? "active" : ""}`} key={item} onClick={() => go(item)}><Icon size={16} /> {t[item]}</button>)}<div className="sidebar-footer"><label className="small">Test route as</label><select className="form-select form-select-sm" value={testRole} disabled={!!currentUser} onChange={(event) => setTestRole(event.target.value as Role)}>{(["ADMIN", "FIELD_OFFICER", "FINANCE", "REVIEWER", "SUPPORT", "MANAGER", "AUDITOR"] as Role[]).map((role) => <option key={role}>{role}</option>)}</select></div></aside><main className="workspace"><header className="topbar"><div><p className="eyebrow">Multi-country humanitarian cash assistance platform</p><h1>{t.command}</h1><small>{currentUser ? `${currentUser.full_name} · ${currentUser.role}` : `Demo capability test · ${effectiveRole}`}</small></div><div className="d-flex gap-2 flex-wrap"><button className="btn btn-outline-primary btn-sm" onClick={() => setLocale(locale === "en" ? "ar" : "en")}><Languages size={16} /> {locale === "en" ? "العربية" : "English"}</button><button className="btn btn-outline-primary btn-sm" onClick={openLogin}>{currentUser ? t.signOut : t.signIn}</button><button className="btn btn-primary btn-sm"><FileDown size={16} /> Export CSV</button></div></header>{content}</main></div>;
}
createRoot(document.getElementById("root")!).render(<App />);
