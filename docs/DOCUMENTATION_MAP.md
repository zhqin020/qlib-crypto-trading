# Documentation Navigation Map

**Visual guide to all documentation in the Qlib Crypto Trading Platform**

---

## Quick Reference

| Need | Document | Location |
|------|----------|----------|
| **Getting Started** | QUICKSTART.md | `/QUICKSTART.md` |
| **Full Documentation** | README.md | `/README.md` |
| **Architecture Overview** | PLATFORM_OVERVIEW.md | `/PLATFORM_OVERVIEW.md` |
| **Deployment Guide** | DEPLOYMENT.md | `/DEPLOYMENT.md` |
| **UI Documentation** | UI_DOCUMENTATION.md | `/docs/UI_DOCUMENTATION.md` |
| **MCP Setup** | MCP_CONFIGURATION.md | `/docs/MCP_CONFIGURATION.md` |
| **State Management** | STATE_BLEED_FIX.md | `/STATE_BLEED_FIX.md` |
| **Port Reference** | PORT_CONFIGURATION.md | `/PORT_CONFIGURATION.md` |
| **Historical Docs** | Archive Index | `/docs/archive/INDEX.md` |

---

## Documentation Structure

```
qlib-2/
├── README.md                          # Main documentation (11,925 bytes)
├── QUICKSTART.md                      # 5-minute getting started (4,045 bytes)
├── PLATFORM_OVERVIEW.md               # Complete architecture (15,848 bytes)
├── DEPLOYMENT.md                      # Production deployment (8,422 bytes)
├── STATE_BLEED_FIX.md                # State management guide
├── PORT_CONFIGURATION.md             # Port reference
├── MCP_SETUP.md                      # MCP server setup (deprecated, see docs/)
├── CLAUDE.md                         # Project guidelines
│
├── docs/
│   ├── UI_DOCUMENTATION.md           # UI/dashboard guide (870 lines)
│   ├── MCP_CONFIGURATION.md          # MCP setup (consolidated)
│   ├── ARCHIVE_REPORT.md             # What was archived and why
│   ├── MCP_CONSOLIDATION_REPORT.md   # MCP doc consolidation
│   ├── UI_CONSOLIDATION_REPORT.md    # UI doc consolidation
│   ├── METRICS_CORRECTIONS_REPORT.md # Metrics audit results
│   ├── LINK_VALIDATION_REPORT.md     # Link health report
│   ├── DOCUMENTATION_MAP.md          # This file
│   │
│   └── archive/
│       ├── README.md                 # Archive introduction
│       ├── INDEX.md                  # Complete archive catalog
│       └── 2024-10/                 # October 2024 archive
│           ├── CURRENT_STATUS.md     # Historical status
│           ├── SOLUTION_PLAN.md      # Completed plan
│           ├── TEST_RESULTS.md       # Historical tests
│           ├── LEARNINGS.md          # Development insights
│           └── [9 more files]        # MCP configs, reports
│
└── [Not documentation]
    ├── UI_FEATURES.md               # (Should be in docs/)
    ├── UI_TESTING_GUIDE.md          # (Should be in docs/)
    ├── REALTIME_UI_COMPLETE.md      # (Should be archived)
    ├── FINAL_DELIVERY.md            # (Should be archived)
    └── [Various .md files]          # Temporary/working docs
```

---

## User Journeys

### Journey 1: First Time Setup (Beginner)

**Goal:** Get the platform running in 5 minutes

```
START
  ↓
QUICKSTART.md (5-minute guide)
  ↓
[Follow commands to download, train, predict]
  ↓
SUCCESS: Trading signals generated!
  ↓
(Optional) Read README.md for full features
```

**Key files:**
1. `/QUICKSTART.md` - Step-by-step setup
2. `/README.md` - Full documentation reference

---

### Journey 2: Understanding the Platform (Intermediate)

**Goal:** Learn architecture and capabilities

```
START
  ↓
README.md (Overview + Quick Start)
  ↓
PLATFORM_OVERVIEW.md (Deep dive)
  ├─→ Technology Stack
  ├─→ Components Breakdown
  ├─→ Data Pipeline
  ├─→ Model Training
  └─→ Deployment Status
  ↓
docs/UI_DOCUMENTATION.md (Web interface)
  └─→ Dashboard features
  └─→ Real-time monitoring
  ↓
docs/MCP_CONFIGURATION.md (MCP integration)
  └─→ Claude Desktop setup
  └─→ Tool descriptions
```

**Key files:**
1. `/README.md` - Platform overview
2. `/PLATFORM_OVERVIEW.md` - Architecture details
3. `/docs/UI_DOCUMENTATION.md` - UI features
4. `/docs/MCP_CONFIGURATION.md` - MCP setup

---

### Journey 3: Production Deployment (Advanced)

**Goal:** Deploy to production environment

```
START
  ↓
README.md (Prerequisites)
  ↓
DEPLOYMENT.md (Full deployment guide)
  ├─→ Local Development
  ├─→ Docker Deployment
  ├─→ Cloud Deployment (AWS/GCP/Azure)
  ├─→ MCP Server Setup
  ├─→ Security
  ├─→ Monitoring
  └─→ Scaling
  ↓
PORT_CONFIGURATION.md (Port reference)
  └─→ Verify ports available
  ↓
docs/MCP_CONFIGURATION.md (MCP setup)
  └─→ Configure Claude Desktop
```

**Key files:**
1. `/DEPLOYMENT.md` - Production guide
2. `/PORT_CONFIGURATION.md` - Port configuration
3. `/docs/MCP_CONFIGURATION.md` - MCP integration

---

### Journey 4: Debugging Issues (Technical)

**Goal:** Troubleshoot specific problems

```
START
  ↓
STATE_BLEED_FIX.md (State management)
  └─→ If: Qlib state issues
  ↓
docs/UI_DOCUMENTATION.md (UI issues)
  └─→ If: Dashboard/API problems
  ↓
docs/MCP_CONFIGURATION.md (MCP issues)
  └─→ If: MCP server won't connect
  ↓
docs/archive/INDEX.md (Historical context)
  └─→ If: Need to understand past decisions
```

**Key files:**
1. `/STATE_BLEED_FIX.md` - State isolation
2. `/docs/UI_DOCUMENTATION.md` - UI troubleshooting
3. `/docs/MCP_CONFIGURATION.md` - MCP debugging
4. `/docs/archive/INDEX.md` - Historical reference

---

### Journey 5: Historical Research (Maintainer)

**Goal:** Understand development history and decisions

```
START
  ↓
docs/archive/README.md (Archive intro)
  ↓
docs/archive/INDEX.md (Complete catalog)
  ├─→ Status Reports (6 files)
  ├─→ Historical Records (3 files)
  └─→ Configuration Updates (4 files)
  ↓
docs/ARCHIVE_REPORT.md (Why things were archived)
  ↓
[Read specific archived documents]
```

**Key files:**
1. `/docs/archive/README.md` - Archive introduction
2. `/docs/archive/INDEX.md` - Complete catalog
3. `/docs/ARCHIVE_REPORT.md` - Archive rationale

---

## Document Categories

### Primary Documentation (Must Read)

| Document | Purpose | Audience | Status |
|----------|---------|----------|--------|
| README.md | Platform overview, quick start | Everyone | ✅ Current |
| QUICKSTART.md | Fast setup guide | Beginners | ✅ Current |
| PLATFORM_OVERVIEW.md | Architecture deep-dive | Developers | ✅ Current |
| DEPLOYMENT.md | Production deployment | DevOps | ✅ Current |

### Technical Guides (Reference)

| Document | Purpose | Audience | Status |
|----------|---------|----------|--------|
| STATE_BLEED_FIX.md | State management | Developers | ✅ Current |
| PORT_CONFIGURATION.md | Port reference | DevOps | ✅ Current |
| docs/UI_DOCUMENTATION.md | UI features & API | Users/Devs | ✅ Current |
| docs/MCP_CONFIGURATION.md | MCP setup | MCP users | ✅ Current |

### Reports (Historical)

| Document | Purpose | Audience | Status |
|----------|---------|----------|--------|
| docs/ARCHIVE_REPORT.md | Archive rationale | Maintainers | ✅ Current |
| docs/MCP_CONSOLIDATION_REPORT.md | MCP doc cleanup | Maintainers | ✅ Current |
| docs/UI_CONSOLIDATION_REPORT.md | UI doc cleanup | Maintainers | ✅ Current |
| docs/METRICS_CORRECTIONS_REPORT.md | Metrics audit | Maintainers | ✅ Current |
| docs/LINK_VALIDATION_REPORT.md | Link health | Maintainers | ✅ Current |

### Archive (Historical Reference)

| Document | Purpose | Status |
|----------|---------|--------|
| docs/archive/INDEX.md | Archive catalog | ✅ Preserved |
| docs/archive/2024-10/* | October 2024 docs | 📦 Archived |

---

## Link Structure

### Active Documentation Links

**Outbound links from active docs:**

```
README.md
  └─→ (no internal links, external only)

QUICKSTART.md
  └─→ README.md (for full documentation)

DEPLOYMENT.md
  ├─→ README.md (general reference)
  └─→ QUICKSTART.md (setup reference)

docs/archive/README.md
  ├─→ INDEX.md (detailed catalog)
  └─→ ../ARCHIVE_REPORT.md (archive details)
```

**See `/docs/LINK_VALIDATION_REPORT.md` for complete link health analysis.**

---

## Document Priorities

### Priority 1: Getting Started (Read First)
1. QUICKSTART.md - 5 minutes
2. README.md - 15 minutes

### Priority 2: Deep Understanding (Read Second)
3. PLATFORM_OVERVIEW.md - 30 minutes
4. docs/UI_DOCUMENTATION.md - 20 minutes

### Priority 3: Production Setup (When Deploying)
5. DEPLOYMENT.md - 20 minutes
6. PORT_CONFIGURATION.md - 5 minutes
7. docs/MCP_CONFIGURATION.md - 15 minutes

### Priority 4: Technical Deep Dives (As Needed)
8. STATE_BLEED_FIX.md - When debugging state issues
9. docs/*_REPORT.md - When understanding changes

### Priority 5: Historical Context (Optional)
10. docs/archive/INDEX.md - For historical reference
11. docs/archive/2024-10/* - For specific historical context

---

## Documentation Standards

### File Naming
- **Active docs:** `DOCUMENT_NAME.md` (root level)
- **Technical guides:** `docs/CATEGORY_TOPIC.md`
- **Reports:** `docs/TOPIC_REPORT.md`
- **Archive:** `docs/archive/YYYY-MM/DOCUMENT.md`

### Document Structure
1. Title (# heading)
2. Metadata (date, status, version if applicable)
3. Overview/Summary
4. Table of Contents (for long docs)
5. Main content with clear sections
6. Examples/Usage (where applicable)
7. Troubleshooting (where applicable)
8. References/Links

### Link Conventions
- ✅ Use relative paths: `[text](../file.md)`
- ✅ Use descriptive link text: `[Deployment Guide](DEPLOYMENT.md)`
- ❌ Avoid bare URLs: Use `[text](url)` format
- ❌ Avoid absolute paths: Use relative instead

---

## Maintenance

### When to Update This Map
- When adding new major documentation files
- When restructuring documentation
- When archiving significant documents
- Quarterly documentation review

### Validation
Run link validation regularly:
```bash
# Check all internal links
grep -rn "\[.*\](.*\.md" --include="*.md" --exclude-dir=venv
```

See `/docs/LINK_VALIDATION_REPORT.md` for complete validation results.

---

## Quick Commands

### Find All Documentation
```bash
find . -name "*.md" -not -path "*/venv/*" -type f | sort
```

### Count Documentation
```bash
find . -name "*.md" -not -path "*/venv/*" -type f | wc -l
# Result: 39 files
```

### Search Documentation
```bash
grep -r "search term" --include="*.md" --exclude-dir=venv
```

### Validate Links
```bash
# See LINK_VALIDATION_REPORT.md for methodology
grep -rn "\[.*\](.*\.md" --include="*.md" --exclude-dir=venv
```

---

## Support

**Questions about documentation?**
- Check this map first
- Read `/docs/LINK_VALIDATION_REPORT.md` for link health
- See `/docs/archive/INDEX.md` for historical context
- Refer to `/README.md` for general platform questions

**Found a broken link?**
1. Search for the old file: `find . -name "oldfile.md"`
2. Check archive: `ls docs/archive/2024-10/`
3. Update link to new location
4. Run link validation

---

**Last Updated:** 2025-10-07
**Maintained By:** Development Team
**Next Review:** Quarterly or after major documentation changes
