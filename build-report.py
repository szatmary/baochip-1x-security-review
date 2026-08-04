#!/usr/bin/env python3
"""Assemble the complete Baochip 1x review.

The agent-authored report (baochip-1x-security-review-auto.md) has a full 117-row index but
detailed writeups for only the 31 critical/high findings, and stops before sections 4-7. This
script keeps those 31 verbatim - they contain real synthesis a generator cannot reproduce -
generates the remaining 86 from the structured reviewer data, and appends sections 4-7 plus
Appendix A.
"""
import json, re, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DISCLOSURE = '''## ⚠️ Fully automated — no human has verified any of this

**Every finding in this repository was produced by AI agents. No human has read, reviewed,
confirmed, or reproduced any finding, any piece of evidence, or any severity rating.**

- All 117 findings were generated, verified and adversarially tested entirely by language models.
- The "independent verification" and "adversarial refutation" described under Method are
  model-versus-model processes. They measurably reduce error — the critical count fell from 9 to 1
  under that filtering — but they do not eliminate it, and they are **not** a substitute for human
  review.
- Nothing has been simulated, synthesised, or tested on silicon.
- Where this repository says a finding was "read against the RTL directly during assembly," that
  refers to work done by the orchestrating model, not by a person.

Treat this as a machine-generated lead list for human triage, not as a verified vulnerability
report. Findings are likely to include false positives, and the severity ratings are model
judgements that have not been calibrated by anyone.
'''
AUTO = open(HERE + '/baochip-1x-security-review-auto.md').read()
APPENDIX = open(HERE + '/appendix-a-sce-key-segments.md').read()
D    = json.load(open(HERE + '/audit-raw.json'))

# ---------------------------------------------------------------- source data
verdict_by_title = {}
for v in D['verifiers']:
    for x in v['verdicts']:
        verdict_by_title[x['title']] = x

pool = []           # every finding, keyed later by (basename, line)
for f in D['finders']:
    dom = f['domain'].split('(')[0].split('—')[0].strip()[:60]
    for x in f['findings']:
        pool.append({**x, '_dom': dom, '_src': 'reviewer'})
for v in D['verifiers']:
    for m in (v.get('missed') or []):
        pool.append({**m, '_dom': '(surfaced by verifier)', '_src': 'verifier'})

byloc = collections.defaultdict(list)
for p in pool:
    byloc[(os.path.basename(p['file']), p.get('line'))].append(p)

# ---------------------------------------------------------------- auto report parts
head   = AUTO.split('## 3. Findings')[0].rstrip()
# make every BAO-### in the finding index an anchor link to its section below
head   = re.sub(r'^\| (BAO-(\d+)) \|', lambda m: '| [%s](#%s) |' % (m.group(1), m.group(1).lower()), head, flags=re.M)
body   = AUTO.split('## 3. Findings', 1)[1]

index = re.findall(r'^\| (BAO-\d+) \| (\w+) \| (.+?) \| `([^`]+)` \|$', AUTO, re.M)
written = {}
for m in re.finditer(r'^### (BAO-\d+) — (.+?)$', body, re.M):
    start = m.start()
    nxt = body.find('\n### BAO-', start + 1)
    written[m.group(1)] = body[start: nxt if nxt != -1 else len(body)].rstrip().rstrip('-').rstrip()


# Four index entries were introduced at the synthesis stage and have no structured reviewer
# record at the cited line. Each was read against the RTL by hand during assembly rather than
# shipped as an unsubstantiated claim; the evidence below is quoted from the source.
SUPPLEMENT = {
 'BAO-046': dict(
   file='rtl/modules/crypto_pke/rtl/mimm.sv', line=121, cwe='CWE-682 Incorrect Calculation',
   threat_actor='T1', confidence='medium',
   description="The Montgomery multiplier's round count is computed with truncating integer "
     "division: `lastrnd` asserts at `nlen/(opt_pl+1) - 1`. Where `nlen` is not an exact multiple "
     "of the pipeline factor `opt_pl+1`, the final partial round is never executed and the top "
     "words of the operand are silently dropped from the reduction. The result is returned as a "
     "normal completion with no error indication.",
   evidence="// mimm.sv:121\n    assign lastrnd = ( mfsmrnd == nlen/(opt_pl+1) - 1 );\n"
     "    assign firstrnd = ( mfsmrnd == 0 );\n"
     "    `theregrn( mfsmrnd ) <= start ? 0 : mfsmrnd+mfsm_s2done;",
   attack_scenario="An operand length that is not a multiple of the configured pipeline factor "
     "yields a silently incorrect modular product. In a signing or key-agreement operation this "
     "produces a mathematically invalid result from valid inputs - the precondition for "
     "Bellcore-style fault analysis, except reachable purely by choosing an operand length, with "
     "no fault injection equipment required.",
   mitigation="RTL: round up rather than truncate, or assert that `nlen mod (opt_pl+1) == 0` and "
     "raise an error otherwise. Firmware: constrain every PKE operand length to an exact multiple "
     "of the configured pipeline factor, and validate results before use."),
 'BAO-047': dict(
   file='rtl/modules/crypto_alu/rtl/aludiv.sv', line=120, cwe='CWE-369 Divide By Zero',
   threat_actor='T1', confidence='medium',
   description="The divider's zero-divisor guard tests `dsidx_msb == 0`, the index of the "
     "divisor's most-significant set bit. That index is 0 both for a divisor of zero and for a "
     "divisor of one, so the guard conflates the two: a legitimate divide-by-one is flagged as an "
     "error, and the genuine zero case is not distinguished by the condition it was written for.",
   evidence="// aludiv.sv:120\n    assign qs0err = ifpresft & ( dsidx_msb == 0 );",
   attack_scenario="Software issuing a divide-by-one receives a spurious error, while the "
     "zero-divisor path is not separately identified. Depending on how `qs0err` is consumed "
     "downstream this either aborts valid operations or fails to abort invalid ones.",
   mitigation="RTL: test the divisor for zero directly rather than inferring it from the MSB "
     "index. Firmware: screen divisor operands for 0 and 1 before submitting them to the ALU."),
 'BAO-052': dict(
   file='rtl/modules/sysctrl/rtl/cms.sv', line=107, cwe='CWE-1221 Incorrect Register Defaults',
   threat_actor='T2/T4', confidence='high',
   description="The chip-mode-select data register's **reset value is the VIRGIN-mode pattern**. "
     "`cmsdatareg` is declared with `CMSDAT_VRGNMODE` as its reset constant, so out of every "
     "reset - and for the entire window before ReRAM supplies a lifecycle value and asserts "
     "`cmsdatavld` - the register holds the least-restrictive lifecycle state rather than a "
     "fail-closed one. A separate `cmsdataregvld` flag tracks whether a real value has arrived, "
     "so the exposure depends on every consumer honouring that flag.",
   evidence="// cms.sv:107 - reset value is the VIRGIN pattern, not a fail-closed default\n"
     "    `theregfull(clk, resetn, cmsdatareg, cms_pkg::CMSDAT_VRGNMODE) <= cmsdatavld ? cmsdata : cmsdatareg;\n"
     "    `theregrn( cmsdataregvld ) <= cmsdatavld ? 1'b1 :    cmsdataregvld;",
   attack_scenario="An attacker who can hold the chip in reset, brown it out, or prevent the "
     "ReRAM lifecycle read from completing leaves the mode register at VIRGIN. Any consumer that "
     "samples `cmsdatareg` without also qualifying on `cmsdataregvld` sees the most permissive "
     "lifecycle state. Security defaults should fail closed; this one fails open.",
   mitigation="RTL: reset to the most restrictive lifecycle pattern, not the least. Firmware: no "
     "mitigation - this is a reset value in fabricated silicon."),
 'BAO-057': dict(
   file='rtl/modules/sec/rtl/mesh.sv', line=55, cwe='CWE-1247 Improper Protection Against Voltage and Clock Glitches',
   threat_actor='T2', confidence='high',
   description="Anti-tamper mesh error indications are combinational and are never latched. "
     "`apterr` is a continuous comparison of the sampled mesh value against the drive register, "
     "and the status register `sr_mlsr` is a bare reduction of it. A tamper event that disturbs "
     "the mesh and then resolves - a probe touched and withdrawn, a transient short - sets the "
     "status only for as long as the disturbance persists, then clears it with no persistent "
     "record.",
   evidence="// mesh.sv:55 and the comparison feeding it - combinational throughout, no latch\n"
     "    apb_sr #(.A('h20), .DW(32), .REVY(1), .SFRCNT(LC*GC/32))  sfr_mlsr (.sr(sr_mlsr), .prdata32(),.*);\n"
     "    ...\n"
     "    assign apterr[i][j] = cr_mlie[i] & ( aptreg[i][j] != cr_mldrv[i] );\n"
     "    assign sr_mlsr[i][k] = |apterr[i][GW*k+GW-1:GW*k];",
   attack_scenario="A physical attacker probes the mesh briefly. Unless firmware happens to poll "
     "`sr_mlsr` during the exact disturbance window, the event leaves no trace. Combined with the "
     "mesh's tamper response being a maskable interrupt that resets to disabled, a transient "
     "physical intrusion is not merely unpunished but unrecorded.",
   mitigation="RTL: latch `apterr` into a sticky, software-clearable fault register. Firmware: no "
     "reliable mitigation - polling cannot be made fast enough to guarantee catching a transient."),
}

def esc(s): return (s or '').strip()
def fence(s):
    s = (s or '').strip()
    if not s: return '_(no verbatim excerpt captured)_'
    s = re.sub(r'^```[a-z]*\n?', '', s); s = re.sub(r'\n?```$', '', s)
    return '```systemverilog\n' + s + '\n```'

VMARK = {'confirmed': 'Independently confirmed by a second reviewer',
         'plausible': 'Verified as written; exploitability not fully established',
         'refuted':   'Refuted'}

L = []; W = L.append
# the automation disclosure must lead the document, immediately under the title
_t, _sep, _rest = head.partition('\n')
W(_t); W(''); W(DISCLOSURE.rstrip()); W(''); W(_rest.strip()); W('')
W('## 3. Findings'); W('')
W('Findings BAO-001 through BAO-031 (the critical and high severities) carry full narrative')
W('analysis, including mitigations split into an RTL fix and what firmware can do on fabricated')
W('silicon. BAO-032 onward are rendered from the structured reviewer record: the same evidence,')
W('attack scenario and verification verdict, in a more compact form.')
W('')

gen = miss = supp = 0
for bid, sev, title, loc in index:
    if bid in written:
        W('<a id="%s"></a>' % bid.lower()); W('')
        W(written[bid]); W(''); W('---'); W(''); continue
    base, _, ln = loc.partition(':')
    try: ln = int(re.sub(r'[^0-9].*$', '', ln))
    except ValueError: ln = None
    cands = byloc.get((base, ln)) or []
    if not cands:
        near = [p for (b, l), ps in byloc.items() if b == base and l and ln and abs(l - ln) <= 12 for p in ps]
        cands = near
    if not cands:
        sup = SUPPLEMENT.get(bid)
        if not sup:
            miss += 1
            W('<a id="%s"></a>' % bid.lower()); W('')
            W('### %s — %s' % (bid, title)); W('')
            W('**Severity: %s** · Location: `%s`' % (sev, loc)); W('')
            W('_Structured record not recovered; see `audit-raw.json`._'); W(''); W('---'); W('')
            continue
        supp += 1
        W('<a id="%s"></a>' % bid.lower()); W('')
        W('### %s — %s' % (bid, title)); W('')
        W('**Severity: %s** | %s | Threat actor: %s | Confidence: %s'
          % (sev, sup['cwe'], sup['threat_actor'], sup['confidence'].title())); W('')
        W('**Location:** `%s:%s`' % (sup['file'], sup['line'])); W('')
        W('*Introduced at the synthesis stage with no structured reviewer record. Read against the RTL')
        W('directly during assembly by the orchestrating model; evidence below is quoted from source.*'); W('')
        W('**Description.** %s' % sup['description']); W('')
        W('**Evidence.**'); W(fence(sup['evidence'])); W('')
        W('**Attack scenario.** %s' % sup['attack_scenario']); W('')
        W('**Mitigation.** %s' % sup['mitigation']); W('')
        W('**Verification.** Read against the RTL during report assembly by the orchestrating model.')
        W('Not independently reviewed, not adversarially tested, and not seen by a human.'); W('')
        W('---'); W('')
        continue
    r = max(cands, key=lambda p: len(p.get('evidence') or ''))
    v = verdict_by_title.get(r['title'])
    gen += 1

    W('<a id="%s"></a>' % bid.lower()); W('')
    W('### %s — %s' % (bid, esc(r['title']) or title)); W('')
    bits = ['**Severity: %s**' % sev]
    if esc(r.get('cwe')): bits.append(esc(r['cwe']))
    if esc(r.get('threat_actor')): bits.append('Threat actor: %s' % esc(r['threat_actor']))
    if esc(r.get('confidence')): bits.append('Confidence: %s' % esc(r['confidence']).title())
    W(' | '.join(bits)); W('')
    W('**Location:** `%s:%s`' % (r['file'], r.get('line'))); W('')
    if r['_src'] == 'verifier':
        W('*Surfaced by the independent verifier, not the original domain reviewer.*'); W('')
    W('**Description.** %s' % esc(r.get('description'))); W('')
    W('**Evidence.**'); W(fence(r.get('evidence'))); W('')
    if esc(r.get('preconditions')):
        W('**Preconditions.** %s' % esc(r['preconditions'])); W('')
    W('**Attack scenario.** %s' % esc(r.get('attack_scenario'))); W('')
    if esc(r.get('mitigation')):
        W('**Mitigation.** %s' % esc(r['mitigation'])); W('')
    if v:
        W('**Verification.** %s. %s' % (VMARK.get(v['verdict'], v['verdict']), esc(v.get('reasoning')))); W('')
        if esc(v.get('correction')):
            W('**Corrections applied by the verifier.** %s' % esc(v['correction'])); W('')
    else:
        W('**Verification.** No independent verdict recorded for this entry.'); W('')
    W('---'); W('')

# ---------------------------------------------------------------- 4. dismissed
refuted = [(t, v) for t, v in verdict_by_title.items() if v['verdict'] == 'refuted']
W('## 4. Considered and dismissed'); W('')
W('Candidate findings investigated by an independent reviewer and withdrawn. Recorded with full')
W('reasoning so they need not be re-investigated, and so the basis for withdrawal is auditable.')
W('')
for t, v in refuted:
    W('### ~~%s~~' % esc(t)); W('')
    W('Reassessed as **%s**.' % (v.get('corrected_severity') or 'n/a').upper()); W('')
    W(esc(v['reasoning'])); W('')
    if esc(v.get('correction')):
        W('**Factual corrections.** %s' % esc(v['correction'])); W('')

# ---------------------------------------------------------------- 5. coverage
W('## 5. Coverage gaps and follow-up'); W('')
W('Two independent critics reviewed the audit itself: one for coverage (what was never looked at)')
W('and one for gaps between documented guarantees and the RTL. Their output follows essentially')
W('unedited, because what an audit *missed* is as material to a reader as what it found.'); W('')
for c in D['critics']:
    # the critics' own '## ' headings collide with this report's section numbering; demote them
    demoted = re.sub(r'^(#{1,3}) ', lambda m: '#' * (len(m.group(1)) + 2) + ' ', c.strip(), flags=re.M)
    W('---'); W(''); W(demoted); W('')

# ---------------------------------------------------------------- 6. supply chain
W('---'); W(''); W('## 6. Build and supply-chain surface'); W('')
W('Reviewed manually; outside the RTL scope but part of the repository.'); W('')
W('| Location | Issue |'); W('|---|---|')
W('| `.github/workflows/main.yml:65-69` | Downloads `linkcheck.sh` from the **`master` branch** of `rust-lang/rust` and executes it — unpinned remote code execution in a job holding `secrets.GITHUB_TOKEN`. |')
W('| `.github/workflows/main.yml:20,44` | `curl \\| tar -xz` of the mdbook release tarball, with no checksum or signature verification. |')
W('| `.github/workflows/main.yml:9,33` | `actions/checkout@master` — a mutable ref rather than a pinned SHA. `peaceiris/actions-gh-pages@v3` is likewise a mutable tag. |')
W('| `.github/workflows/main.yml` | No `permissions:` block; the job runs with default `GITHUB_TOKEN` scope and deploys to `gh-pages`. |')
W('')
W('**Mitigating factors.** The trigger is `on: [push]` only, not `pull_request`, so untrusted forks')
W('cannot reach it; the blast radius is limited to compromise of one of the four upstream fetch')
W('points. All five git submodules are pinned by commit SHA, which is correct.'); W('')
W('**Not a finding.** The `eval(` occurrences under `rtl/scripts/headergen/` are a class method on')
W('an expression AST, not the Python builtin.'); W('')

# ---------------------------------------------------------------- 7. method + limits
W('## 7. Method, limitations and handling'); W('')
W('### 7.1 Method'); W('')
W('16 parallel domain reviewers over the RTL, each followed by an **independent verifier**')
W('instructed to re-derive every finding from source and to default to *refuted* where it could')
W('not substantiate the claim itself. Every critical and high finding then faced a **two-lens')
W('adversarial panel** — one lens testing code truth, one testing exploitability — whose explicit')
W('instruction was to refute. A finding survived only where not every lens refuted it. Two critics')
W('then assessed coverage and documented-guarantee-versus-RTL (§5).'); W('')
W('The filtering was not cosmetic: **the critical count fell from 9 to 1** under adversarial')
W('review. Verifier verdicts across all 90 primary findings were %d confirmed, %d plausible, %d'
  % (sum(1 for v in verdict_by_title.values() if v['verdict'] == 'confirmed'),
     sum(1 for v in verdict_by_title.values() if v['verdict'] == 'plausible'),
     len(refuted)))
W('refuted; verifiers additionally surfaced %d findings the domain reviewers had missed. Of 40'
  % sum(len(v.get('missed') or []) for v in D['verifiers']))
W('adversarial votes cast, 34 upheld the finding and 6 refuted it, with 24 rating exploitability')
W('`practical` — reachable by an ordinary attacker rather than requiring exotic equipment.'); W('')
W('### 7.2 Limitations'); W('')
W('- **Static source review only.** No simulation, formal verification, synthesis, netlist review')
W('  or silicon testing was performed. **No finding here has been demonstrated on hardware.**')
W('- **Redacted constants.** `docs/src/ch00-00-rtl-overview.md:5` states the RTL "redacts some')
W('  closed-source components." Constants reading `\'0` may be placeholders rather than silicon')
W('  values — one candidate critical was withdrawn on exactly this basis (§4). Any finding resting')
W('  on a suspicious zero constant is a **question for the vendor**, not an assertion.')
W('- **Black boxes**, absent from the repository and unreviewable: ARM NIC-400 (`nic400_1`),')
W('  `ahb_bmx33_intf`, `ahb_bmxif_intf`, the `CM7AAB` AXI→AHB bridge, `cm7top`,')
W('  `sdvt_spi_master_core`, `trbcx1r32_daric_wrapper` internals. **`hauser`/`AxUSER` propagation')
W('  through the two AHB matrices and CM7AAB cannot be proven from open RTL**, and several')
W('  findings depend on it.')
W('- Third-party IP under `rtl/ips/` and the generated VexRiscv netlist received targeted review only.')
W('- Testbench code was read for understanding but excluded from the attack surface.')
W('- Severity ratings have not been through a formal calibration pass.'); W('')
W('### 7.3 Handling'); W('')
W('Results are published openly. Because the')
W('part is fabricated and cannot be respun, findings that admit a firmware mitigation are the')
W('actionable ones; each finding states separately what an RTL fix would be and what firmware can')
W('do on existing silicon, and says so explicitly where the answer is that nothing can.'); W('')

# ---------------------------------------------------------------- appendix A
appx = APPENDIX
if appx:
    W('---'); W(''); W(appx.strip()); W('')

open(HERE + '/baochip-1x-security-review-full.md', 'w').write('\n'.join(L))
print('index entries      %d' % len(index))
print('kept verbatim      %d (agent-authored critical/high)' % len(written))
print('generated          %d' % gen)
print('supplemented       %d (hand-verified during assembly)' % supp)
print('unmatched          %d' % miss)
print('dismissed (§4)     %d' % len(refuted))
print('critics (§5)       %d' % len(D['critics']))
print('appendix A         %s' % ('ported' if appx else 'MISSING'))
