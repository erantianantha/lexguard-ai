"""
Expanded Legal Knowledge Base for LexGuard RAG.
Covers: employment, SaaS, privacy, IP, real-estate, freelance, insurance, platform ToS.
"""

LEGAL_KNOWLEDGE = [
    # ── Employment ────────────────────────────────────────────────────────────
    {
        "id": "emp_noncompete_1",
        "topics": ["non-compete", "employment", "restriction", "post-employment"],
        "text": (
            "Non-compete clauses in employment agreements restrict employees from working for "
            "competitors or starting competing businesses for a defined period after termination. "
            "Courts scrutinise these clauses for reasonableness in duration (typically 6–24 months), "
            "geography (local vs. global), and scope (full industry vs. specific role). "
            "Overly broad non-competes are unenforceable in many jurisdictions (e.g., California bans them). "
            "Standard market practice: 6–12 months, limited geography, role-specific activities only."
        ),
    },
    {
        "id": "emp_ipownership_1",
        "topics": ["ip ownership", "work for hire", "intellectual property", "employment"],
        "text": (
            "Broad IP assignment clauses that transfer ownership of all inventions — including those "
            "created on personal time unrelated to the employer's business — are increasingly "
            "scrutinised. Several US states (CA, DE, IL, MN, NC, WA) have statutes protecting "
            "employees' rights to inventions made without company resources and unrelated to company business. "
            "A balanced clause limits assignment to inventions related to the employer's current or "
            "reasonably anticipated business, or created using company resources."
        ),
    },
    {
        "id": "emp_termination_1",
        "topics": ["termination", "at-will", "employment", "notice period"],
        "text": (
            "At-will employment termination clauses allow either party to end the relationship at "
            "any time without cause. However, implied obligations of good faith and fair dealing "
            "apply in many jurisdictions. Severance obligations, WARN Act notice requirements "
            "(60 days for layoffs affecting 50+ employees in the US), and anti-discrimination laws "
            "constrain unilateral termination. Standard practice: 2–4 weeks notice or pay in lieu."
        ),
    },
    # ── SaaS / Technology ────────────────────────────────────────────────────
    {
        "id": "saas_sla_1",
        "topics": ["SLA", "uptime", "service level", "availability", "SaaS"],
        "text": (
            "Service Level Agreements (SLAs) in SaaS contracts define uptime commitments, typically "
            "99.5%–99.99%. Below these thresholds, customers are entitled to service credits, "
            "not monetary damages. Clauses excluding 'planned maintenance' or 'force majeure' "
            "from uptime calculations significantly dilute the SLA value. "
            "Best practice: credits ≥ 10× the value of downtime, escalating with severity; "
            "the right to terminate if SLA is missed for 3+ consecutive months."
        ),
    },
    {
        "id": "saas_datarights_1",
        "topics": ["data rights", "data ownership", "SaaS", "customer data", "license"],
        "text": (
            "SaaS agreements often grant providers broad licences over customer data for purposes "
            "beyond service delivery (e.g., product improvement, analytics, training AI models). "
            "A balanced clause limits the provider's use to: (1) providing the service, "
            "(2) troubleshooting with consent, (3) aggregated anonymised analytics. "
            "Customers should retain full ownership and be able to export all data in portable "
            "formats within 30 days of termination."
        ),
    },
    {
        "id": "saas_autorenewal_1",
        "topics": ["auto-renewal", "subscription", "cancellation", "lock-in", "SaaS"],
        "text": (
            "Auto-renewal clauses automatically extend subscription agreements for additional terms "
            "unless cancelled within a notification window. Problematic clauses shorten notice "
            "windows to 7–14 days or obscure renewal conditions. "
            "Standard practice: 30–60 day cancellation window before renewal; "
            "written notification of upcoming renewal at least 30 days in advance. "
            "FTC's 'Click-to-Cancel' rule (2024) requires subscription cancellation to be as easy "
            "as sign-up."
        ),
    },
    {
        "id": "saas_liability_1",
        "topics": ["liability limitation", "cap", "damages", "indemnification", "SaaS"],
        "text": (
            "Mutual limitation-of-liability clauses in SaaS agreements typically cap damages at "
            "12 months of fees paid. Providers often exclude consequential, indirect, or "
            "special damages entirely. One-sided caps — where the provider's liability is "
            "capped but the customer's obligations (e.g., payment, indemnification of IP claims) "
            "are uncapped — create significant imbalance. "
            "Carve-outs from caps should exist for: data breaches, gross negligence, willful misconduct, "
            "and death/personal injury."
        ),
    },
    # ── Privacy & Data ────────────────────────────────────────────────────────
    {
        "id": "privacy_gdpr_1",
        "topics": ["GDPR", "data protection", "privacy", "consent", "EU"],
        "text": (
            "Under GDPR (EU), data processors must have a lawful basis for processing personal data. "
            "Consent must be freely given, specific, informed, and unambiguous. "
            "Pre-ticked boxes, bundled consent, or consent as a condition of service are invalid. "
            "Data subjects have rights to: access, rectification, erasure ('right to be forgotten'), "
            "portability, restriction, and objection. Data breach notification is required within "
            "72 hours of discovery. Fines up to €20M or 4% of global annual turnover."
        ),
    },
    {
        "id": "privacy_ccpa_1",
        "topics": ["CCPA", "California", "privacy", "consumer rights", "data sale"],
        "text": (
            "Under CCPA/CPRA, California consumers have rights to: know what personal data is "
            "collected and how it's used, delete personal data, opt-out of sale/sharing of data, "
            "correct inaccurate information, and limit use of sensitive personal information. "
            "Businesses cannot discriminate against consumers who exercise CCPA rights. "
            "Penalties: $2,500 per unintentional violation, $7,500 per intentional violation. "
            "Applies to businesses with >$25M revenue, >50K consumers/devices, or earning >50% "
            "revenue from selling data."
        ),
    },
    {
        "id": "privacy_thirdparty_1",
        "topics": ["third-party sharing", "data transfer", "data broker", "privacy"],
        "text": (
            "Broad third-party data sharing clauses that allow sharing with 'affiliates, partners, "
            "and service providers' without restriction create significant privacy risk. "
            "Best practice: limit sharing to named categories of recipients with specific purposes; "
            "require sub-processor agreements with equivalent data protection standards; "
            "prohibit sharing for advertising/marketing without explicit opt-in consent; "
            "maintain and publish a list of sub-processors."
        ),
    },
    # ── Arbitration & Dispute Resolution ────────────────────────────────────
    {
        "id": "arb_mandatory_1",
        "topics": ["arbitration", "dispute resolution", "class action waiver", "legal rights"],
        "text": (
            "Mandatory arbitration clauses require disputes to be resolved through private arbitration "
            "rather than courts. These clauses often include class action waivers, preventing "
            "consumers or employees from joining class actions. "
            "This removes access to: jury trials, class action suits, public court records, "
            "meaningful appeal rights, and regulatory oversight. "
            "CFPB regulations have attempted to limit these in financial products. "
            "One-sided arbitration clauses (provider chooses arbitrator, loser-pays provisions, "
            "short filing deadlines) are often unenforceable under unconscionability doctrine."
        ),
    },
    # ── Intellectual Property ─────────────────────────────────────────────────
    {
        "id": "ip_freelance_1",
        "topics": ["IP", "freelance", "work for hire", "copyright", "ownership"],
        "text": (
            "Under US copyright law, 'work for hire' doctrine applies to works created by employees "
            "within the scope of employment and to nine specific categories of commissioned works "
            "with a written work-for-hire agreement. Freelancers/independent contractors retain "
            "copyright by default. Broad IP assignment clauses in freelance contracts that "
            "transfer all rights — including pre-existing IP or independently developed tools — "
            "go beyond legal defaults. A balanced clause: assigns only the specific deliverables, "
            "licenses (not assigns) pre-existing tools, and clearly defines the scope."
        ),
    },
    # ── Force Majeure ──────────────────────────────────────────────────────────
    {
        "id": "force_majeure_1",
        "topics": ["force majeure", "performance", "risk allocation", "excused delay"],
        "text": (
            "Force majeure clauses excuse non-performance due to extraordinary events beyond a party's "
            "control. Problematic clauses include broad, subjective triggers ('events Provider deems "
            "beyond its control'), one-sided application (only the provider can invoke), or "
            "list pandemic/market conditions/staffing shortages as excused events. "
            "Standard practice: balanced application to both parties, objective triggering criteria, "
            "obligation to use reasonable efforts to minimise impact, time limits (30–90 days) "
            "before the other party may terminate."
        ),
    },
    # ── Modification & Amendment ──────────────────────────────────────────────
    {
        "id": "amendment_1",
        "topics": ["amendment", "modification", "unilateral change", "terms of service"],
        "text": (
            "Unilateral modification clauses allow one party to change the agreement terms without "
            "counterparty consent. This is extremely high-risk in consumer and SaaS contracts. "
            "Best practice: amendments require written consent of both parties; "
            "if provider may update terms, customer must receive 30 days' prior notice, "
            "have the right to terminate without penalty if they object, "
            "and continued use after notice constitutes acceptance only for material changes."
        ),
    },
    # ── Insurance / Financial ─────────────────────────────────────────────────
    {
        "id": "insurance_exclusion_1",
        "topics": ["insurance", "exclusion", "coverage", "financial risk"],
        "text": (
            "Insurance policy exclusion clauses limit coverage for specific events, conditions, or "
            "types of damages. Common problematic exclusions include: pre-existing condition "
            "exclusions in health insurance (banned under ACA for most plans), retroactive "
            "exclusions added mid-policy period, vague exclusion language ('faulty workmanship', "
            "'gradual deterioration'), and anti-concurrent causation clauses that deny coverage "
            "when an excluded peril contributes to a covered loss."
        ),
    },
    # ── Real Estate / Rental ──────────────────────────────────────────────────
    {
        "id": "rental_security_1",
        "topics": ["rental", "security deposit", "landlord", "tenant", "real estate"],
        "text": (
            "Security deposit clauses should comply with jurisdiction-specific statutory limits "
            "(typically 1–3 months' rent), return timelines (14–30 days after move-out), "
            "and itemisation requirements for deductions. Problematic clauses include: "
            "non-refundable deposits (often illegal for rental security), vague damage definitions, "
            "landlord's unilateral authority to determine deductions, and waiver of tenant rights. "
            "Most jurisdictions require itemised written notice of deductions within the statutory period."
        ),
    },
]
