# BAOCHIP-1X — SECRET / ASSET FLOW MAP

All paths below are relative to the repository root. Verified against RTL as read; `ifdef FPGA` branches noted where they differ from the ASIC build.

---

## 0. ADDRESS ANCHORS (needed to read the rest)

`rtl/asic_top/rtl/daric_cfg_pkg.sv:48-55` — APB/AHB peripheral map:
```
'{idx: 32'd2 , start_addr: 32'h4002_0000, end_addr: 32'h4003_0000}, // sce
'{idx: 32'd0 , start_addr: 32'h4000_0000, end_addr: 32'h4001_0000}  // rrc
```
`rtl/asic_top/rtl/daric_cfg_pkg.sv:63-66` — memory map: reram `0x6000_0000..0x6040_0000`, sram `0x6100_0000..0x6120_0000`, dtcm `0x2000_0000`, itcm `0x0000_0000`.

`rtl/modules/crypto_top/rtl/sce.sv:60-64` — SCE internal decode (add `0x4002_0000`):
```
'{idx: 32'd2 , start_addr: 32'h0000_4000, end_addr: 32'h0000_6000}, // pkeram
'{idx: 32'd1 , start_addr: 32'h0000_0000, end_addr: 32'h0000_2800}, // ram
'{idx: 32'd0 , start_addr: 32'h0000_8000, end_addr: 32'h0000_FFFF}  // ctrl
```
APB sub-decode is `paddr[14:12]` (`sce.sv:179` `apb_mux #(.PAW(15),.DECAW(3))`), giving:

| Addr | Block | RTL |
|---|---|---|
| `0x4002_0000-0x4002_27FF` | **SCERAM** (all 18 key/data segments) | `sce.sv:414-435` |
| `0x4002_4000-0x4002_5FFF` | **PKERAM** (2×512×64) direct AHB | `sce.sv:495` / `pke.sv:1511,1529` |
| `0x4002_8000` | glbsfr: `scemode`, `ar_reset`/`ar_clrram`, truststate | `sce_glbsfra.sv` |
| `0x4002_9000` | scedma (ich/xch/sch descriptors) | `scedma.sv` |
| `0x4002_B000` | combohash / HMAC / keyidx | `combohasha.sv` |
| `0x4002_C000` | PKE control | `pke.sv` |
| `0x4002_D000` | AES control + mask seed | `aes.sv` |
| `0x4002_E000` | **TRNG** (raw entropy buffer at `+0x30`) | `trng.sv` |
| `0x4002_F000` | ALU | `alu.sv` |

AMBA master IDs (`daric_cfg_pkg.sv:72-84`): `CM7A=2, VEXI=3, VEXD=4, SCEA=5, SCES=6, CM7P=8, CM7D=9, UDMA=A, UDCA=B, SDDC=C, VEXP=D`.

---

## 1. STORAGE ELEMENTS THAT CAN HOLD A SECRET

### 1.1 SCERAM — the central secret store (1× 2560×32b, `sce_sceram_10k`)

Instantiated `rtl/modules/crypto_top/rtl/sce.sv:414-435`; macro wrapper `rtl/modules/crypto_top/rtl/cryptoram.sv:216-226`.

Segment table `rtl/modules/crypto_top/rtl/scedma_pkg.sv:211-254`. Word offsets and resulting AHB byte addresses:

| Seg | id | words | byte range | contents |
|---|---|---|---|---|
| LKEY | 0 | 0–63 | `4002_0000-00FF` | long key (FIFO id 0) |
| KEY | 1 | 64–127 | `4002_0100-01FF` | HMAC key |
| **SKEY** | 2 | 128–191 | `4002_0200-02FF` | **secret key (`ST_KI`)** |
| **SCRT** | 3 | 192–255 | `4002_0300-03FF` | **secret/HMAC compare buffer (`ST_KI`)** |
| MSG | 4 | 256–383 | `4002_0400-05FF` | message (FIFO id 1) |
| HOUT | 5 | 384–447 | `4002_0600-06FF` | hash output |
| SOB | 6 | 448–511 | `4002_0700-07FF` | secure output buffer |
| **PKB** | 8 | 512–767 | `4002_0800-0BFF` | **PKE key buffer (`ST_KI`)** |
| PIB | 9 | 768–1279 | `4002_0C00-13FF` | PKE input |
| POB | 11 | 1280–1535 | `4002_1400-17FF` | PKE output |
| PSOB | 12 | 1536–1791 | `4002_1800-1BFF` | PKE secure output |
| **AKEY** | 13 | 1792–1855 | `4002_1C00-1CFF` | **AES key + IV (`ST_KI`)** |
| AIB | 14 | 1856–1919 | `4002_1D00-1DFF` | AES input (FIFO 2) |
| AOB | 15 | 1920–1983 | `4002_1E00-1EFF` | AES output (FIFO 3) |
| **RNGA** | 16 | 1984–2239 | `4002_1F00-22FF` | **TRNG output pool (FIFO 4)** |
| **RNGB** | 17 | 2240–2495 | `4002_2300-26FF` | **TRNG output pool (FIFO 5)** |

`PCON` (7) and `PSIB` (10) have `segsize = 0` (`scedma_pkg.sv:219,223`) — unreachable via address decode.

### 1.2 Per-engine private RAMs (no bus port at all)

| RAM | Size | Instantiated | Holds |
|---|---|---|---|
| ARAM `sce_aesram_1k` | 256×32 | `aes.sv:512-528` | AES key sched @word `0x08` (8 wds, `aes.sv:67`), plaintext @`0x00`, IV @`0x04`, ct @`0x44`, OFB X @`0x48` |
| HRAM `sce_hashram_3k` | 1024×32 | `combohasha.sv:854-870` | hash state `RAMSEG_ST=0x200`, msg `0x220` (`hash_pkg.sv:105-106`); HMAC ipad/opad key |
| PRAM `sce_pkeram_4k` ×2 | 2×512×64 | `pke.sv:1511,1529` | RSA/ECC operands, private exponent, modulus |
| ALURAM `sce_aluram_3k` ×2 | 2×1024×32 | `alu.sv:580,598` | bignum intermediates |
| **MIMM DPRAM `sce_mimmdpram`** | 256×64 (+parity) | `mimm.sv:273`, `mimm.sv:624` → `mimm_dpram.sv:18-138` | **Montgomery multiplier intermediates — key-dependent** |

### 1.3 Pipeline / flop-level secret holders

- `aes.sv:242` `acore_ramwdat`, `acore_ramrdat`; `AesCore` round state and `RoundKeyIn/RoundKeyOut` (`rtl/modules/crypto_aes/rtl/AesDataPath.v:22-26,153-176`). No zeroization on any event.
- `sce_dmachnl.sv:158-173` `thedatreg` — the 32-bit DMA staging register. Holds the last word moved by **any** channel (key words included). Only cleared on `transstart|transdone` **and only in XOR mode** (`sce_dmachnl.sv:159-160`); in non-XOR mode it persists (`rprdpl1vld ? rprdatx : thedatreg`).
- `trng.sv:361` `chnlo_rpres.segrdat` register — holds the last 32-bit TRNG output word indefinitely.
- `data_buf.v:32,47` `buf_data[255:0]` — **the 256-bit raw entropy / DRBG seed register**.
- `lfsr129.v:47` `lfsr_chain[128:0]` — DRBG state.
- `ctr_aes.v` internal AES key/counter (`postprocess.v:55-63` `aes_key`, `aes_text_in`, `aes_text_out[255:0]`).
- `rrc.sv:338,561` `ahb_rd_buf[255:0]` — **holds the raw 256-bit ReRAM word just fetched, including key slots, before any access check is applied.**
- `rrc.sv:348` `acram_wrbuf[255:0]`, `rrc.sv:346` `acram_rdata[63:0]` — key-slot access-control descriptors.
- `dkpc.sv:151-166` `evfifo` (11-deep, 21-bit) — keypad node index + 16-bit timestamp per press/release. This is the **PIN entry channel**, in the AO domain.

### 1.4 Always-on domain

- **`aobureg`** — `rtl/modules/ao/rtl/aobureg.sv:26,35`:
  ```
  bit [REGCNT-1:0][31:0] cr_buregs;
  apb_cr #(.A('h0), .DW(32), .SFRCNT(REGCNT))   sfr_bureg      (.cr( cr_buregs ), .prdata32(),.*);
  ```
  8×32b = 256 bits of battery-backed scratch, reset only by `porresetn` (`ao_top.sv:236`). Plain R/W APB, `sfrlock` hard-tied 0 (`aobureg.sv:30`).
- **`aoram`** — 2×1024×36 (`ao_top.sv:248-266`, controller `rtl/modules/ao/rtl/aoram.sv`). 8 KB of always-on SRAM, `ret1n` tied `1'b1` (`ao_top.sv:264`) i.e. no retention-only mode; contents survive main-domain reset and sleep.

### 1.5 ReRAM (non-volatile)

`rtl/modules/rrc/rtl/rrc.sv`. Regions by `haddr[31:16]`:
- `PM_KEY_REGION = 16'h603F` (`rrc.sv:355`) — **key slots**, 32 B each.
- `PM_DATA_REGION`, code region `< 20'h603D_A` (`rrc.sv:644`), info region, cfg region `PM_CFGD/CFGK_REGION = {16'h603D, 2'b11}` (`rrc.sv:806-807`).
- `PM_KS_BA = 32'h603f0000` is hard-wired into the hash engine (`sce.sv:443`), so the SCE fetches HMAC key-store words straight out of the ReRAM key region over AXI.
- **ACRAM** `acram2kx64` (`rrc.sv:424`) — 2048×64 mirror of the per-slot access-control descriptors, loaded at boot by the BIST-read FSM (`rrc.sv:360`).
- NVR config words: `nvrcfg_pkg::nvrcfg_t` (`rtl/modules/sysctrl/rtl/nvrcfgs.sv:118-147`), word 10 = `cfgsce`, word 12 = `cfgcore`, word 6 = `cfgrrsub`.

---

## 2. WHO CAN READ EACH ELEMENT

### 2.1 The three SCE modes

`sce_sec.sv:54-56`:
```
assign mode_non = ( scemode == 0 );
assign mode_xls = ( scemode == 1 );
assign mode_sec = ( scemode[1] == 1 );
```
`scemode` = `cr_scemode` from `sce_glbsfra.sv:78`:
```
apb_cr #(.A('h00), .DW(2))      sfr_scemode     (.cr(cr_scemode), .prdata32(), .sfrlock(~devmode & (|cr_scemode)), .*);
```
Write-once-nonzero (locked once any bit set, unless devmode).

### 2.2 The AHB owner gate

`sce_sec.sv:70-77`:
```
assign ahbscpvld = ahbs.hsel & ahbs.htrans[1] & ahbs.hreadym & ahbs.hready ;

assign ahben =  mode_non ? 1'b1 :
                        ((sceusersel == 0 ) ? ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) : ( ahbs.hauser == daric_cfg::AMBAID4_VEXD )) &
                        ((sceusersel == 0 ) ? ( coreuser_cm7 == sceuser ) : ( coreuser_vex == sceuser ));

ahb_gate #(.AW(32),.DW(32)) ahbsgate(.ahben,.ahbslave(ahbs),.ahbmaster(ahbm));
assign ahbs_lock = devmode[0] ? 1'b0 : ~ahben;
```
Owner latch, `sce_sec.sv:58-64`:
```
assign sceuserlock = ( scemodereg == 0 ) && ~( scemode == scemodereg ) ;
`theregrn( scemodereg ) <= scemode;

`theregrn( {coreuserselreg, coreuserreg} ) <=   ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) ? { 1'b0, coreuser_cm7 } :
                                                ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_VEXD ) ? { 1'b1, coreuser_vex } : {coreuserselreg, coreuserreg};

`theregrn( {sceusersel, sceuser} ) <= sceuserlock ? {coreuserselreg, coreuserreg} : {sceusersel, sceuser};
```
**In `mode_non` the entire SCE — all of SCERAM including SKEY/SCRT/AKEY/PKB, all engine SFRs — is open to every AHB master, and `ahben` is unconditionally 1.** The owner is whatever CPU last did an AHB address phase before the `0→nonzero` `scemode` transition; `coreuserreg` is updated on any qualifying access in the multi-cycle window between address phase and the APB `scemode` write landing.

### 2.3 SCERAM DMA-channel access control

`rtl/modules/crypto_top/rtl/scedma_ac.sv:40,45-59,66`:
```
assign nvrrule_enable = (nvracrules[29] == 8'h5a);
...
assign chnlinsegid[i] = chnlinreq[i].segcfg.segid;
assign chnlacrule = chnlacrules[chnlinsegid[i]][i] ;
assign chnlac[i] = acenable ? chnlacrule : '1;
...
assign chnloutreq[i].segrd     = chnlinreq[i].segrd  & chnlac[i]   ;
assign chnloutreq[i].segwr     = chnlinreq[i].segwr  & chnlac[i]   ;
...
assign chnlinres[i].segrdat    = chnlac[i] ? chnloutres[i].segrdat    : '0 ;
...
assign chnlacrules[j] = nvrrule_enable ? nvracrules[j] : ACRULEs[j].accessrule;
```
`acenable = mode_sec` (`sce.sv:370`). **All segment access control is disabled in `mode_non` and `mode_xls`.**

Static rules `scedma_pkg.sv:290-310`; bit index `i` = channel, `[0:7]` ordering (0/1 = AHB rd/wr, 2/3 = AXI-gnl rd/wr, 4/5 = AXI-sec rd/wr, 6/7 = ich rd/wr, per `scedma_pkg.sv:278-282`):

| Seg | rule | readable from bus? |
|---|---|---|
| LKEY, KEY, SKEY, SCRT, MSG, PCON, PKB, PIB, PSIB, AKEY, AIB | `8'b01_01_01_01` | **write-only** (no read on any channel) |
| HOUT | `8'b01_00_00_10` | AHB write + ich read only |
| SOB, PSOB | `8'b10_00_10_00` | AHB read + AXI-sec read |
| POB | `8'b00_00_00_10` | ich read only |
| AOB | `8'b10_10_10_10` | read on all four channels |
| RNGA, RNGB | `8'b10_11_10_10` | read on all; AXI-gnl also write |

Two structural gaps in this table:
- `scedma_pkg.sv:300` — the entry at array index 8 (which the lookup uses for **PKB**) is written `'{ segid:SEGID_KEY , accessrule: 8'b01_01_01_01 }`; the `segid` field is decorative (the lookup is `chnlacrules[segid]`, indexed positionally), so the rule value happens to be right, but the table is self-inconsistent.
- `chnlacrules` is an 18-entry array indexed by an **8-bit** `segid` (`scedma_ac.sv:45-46`). `segid ≥ 18` is out of range.

Engine channels **bypass this block entirely.** `sce.sv:377-382` wires only `chnlreq[0:CHNLACCNT-1]` (= 0..7) through `scedma_ac`; the engine ports `ramreq[8..16]` (hash 8/9, PKE 10/11, AES 12/13, TRNG 14, ALU 15/16 — `sce.sv:454-565`) go straight into `sce_memc`.

### 2.4 Unbounded segment pointers → address escape

`rtl/modules/crypto_top/rtl/sce_dmachnl.sv:120-129`:
```
assign rpseg = therpsegcfg.segaddr;
assign wpseg = thewpsegcfg.segaddr;

`theregrn( rpptr ) <= ( rpptr > therpsegcfg.segsize ) ? 0 :
                      chnlstart ? thecfg.rpptr_start :
                      transdone ? (( rpptr == therpsegcfg.segsize - 1 ) ? 0 : rpptr + 1 ) : rpptr;

`theregrn( wpptr ) <= ( wpptr > thewpsegcfg.segsize ) ? 0 :
                      chnlstart ? thecfg.wpptr_start :
                      transdone ? (( wpptr == thewpsegcfg.segsize - 1 ) ? 0 : wpptr + 1 ) : wpptr;
```
The range clamp is evaluated one cycle **after** `rpptr_start` is loaded, so the first access of every transfer uses the raw, unclamped 12-bit start pointer. Final address is a raw add with no check:

`rtl/modules/crypto_top/rtl/sce_memc.sv:212`:
```
assign ramm_addr[gvk] = arbm_dat[gvk].segaddr + arbm_dat[gvk].segptr;
```
`adr_t` is 12 bits (`scedma_pkg.sv:23,29`), so `segaddr + segptr` covers the whole 2560-word SCERAM.

Software-writable pointer sources with no bound:
- ich channel: `scedma.sv:114-115` `sfr_ich_rpstart`/`sfr_ich_wpstart`, `.DW(AW)` = 12 bits, plus `sfr_ich_segid` (`scedma.sv:113`) which selects the segid **used by the AC check**, decoupled from the address actually generated.
- xch/sch: `scedma.sv:102,109` `sfr_xch_segstart` / `sfr_sch_segstart`.
- AES: `aes.sv:157` `apb_cr #(.A('h30), .DW(scedma_pkg::AW), .SFRCNT(4)) sfr_segptr` → `cr_segptrstart[0..3]` used at `aes.sv:323,332,341,371,386`.
- Hash: `combohasha.sv:221` `sfr_segptr` `.SFRCNT(SEGCNT+1)`.
- PKE: `pke.sv:311` `sfr_segptr` `.SFRCNT(5)`.

Also `scedma.sv:277-278` indexes `SEGCFGS[ichcr_rpsegid]` / `SEGCFGS[ichcr_wpsegid]` with 8-bit values into an 18-entry array.

### 2.5 PKERAM direct AHB window

`sce.sv:495-496` → `pke.sv:1408-1410`:
```
assign ahbs_ramwr = ahbslock ? '0 : |hramwen;
assign ahbs_ramrd = ahbslock ? '0 : hramcs & ~ahbs_ramwr;
assign ahbs_en    = ahbslock ? '0 : hramcs;
```
`ahbslock = pkeahbslock = devmode_sce[3] ? '0 : mode_sec` (`sce.sv:138`). **In `mode_non` / `mode_xls` the entire 8 KB PKE working RAM is directly readable at `0x4002_4000`.**

### 2.6 ALU key-segment guard

`alu.sv:512-517`:
```
`theregrn( aluinvld ) <= mode_sec & (
        ( scedma_pkg::SEGCFGS[cr_segcfg[0][15:12]].segtype == scedma_pkg::ST_KI )| ... );
assign aluvld = ~aluinvld;
```
Only active when `mode_sec`, and disableable via `alusec = devmode_sce[4] ? '0 : mode_sec` (`sce.sv:139`).

### 2.7 ReRAM key-slot access control

`rrc.sv:684-689`:
```
assign keysel = ( haddr_reg[31:16] == PM_KEY_REGION );
...
assign datacfg = haddr_reg[5] ? acram_rdata[63:32] : acram_rdata[31:0];
assign keycfg = haddr_reg[5] ? acram_rdata[63:32] : acram_rdata[31:0];
```
`rrc.sv:712-720`:
```
assign key_access_error_pre = (((coreuser_in[7:4] & userid_k[7:4])==0) & (ahb_write_flag | ahb_read_flag) |
                            ahb_read_flag & ((core_rd_dis_k & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg)) |
                            ahb_write_flag & ((core_wr_dis_k & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg)) |
                            ahb_read_flag & scesel & (sce_rd_dis_k | (!sce_sec_op) | (keytype_in != keytype_k)) |
                            ahb_write_flag & scesel & (sce_wr_dis_k | (!sce_sec_op) | (keytype_in != keytype_k)) |
                            (!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))) & data_op & keysel & (userid_k[7:4] != 4'h0);
assign key_access_error = key_access_error_pre;
```
Three properties downstream finders should note:
1. The whole expression is `& (userid_k[7:4] != 4'h0)` — a key slot whose ACRAM descriptor has a zero user field is **unconditionally accessible**. Erased/default ACRAM (all zeros) yields `userid_k = 0`.
2. `keytype_in = {3'h0, axid_reg[6:2]}` (`rrc.sv:675`) and `axim.arid = cr_segid` (`scedma_amba.sv:385,401`), where `cr_segid` is a plain SFR (`scedma.sv:101,108`). The "key type" the ReRAM matches is chosen by software.
3. `sce_sec_op = axprot_reg[0] & mode_sec` (`rrc.sv:681`) and `cr_axprot = mode_sec ? cr_opt[9:8]|3'h0 : mode_xls ? 3'h2|cr_opt[8] : 3'h2` (`scedma_amba.sv:305`) — `axprot[0]` is software-supplied via `sfr_sch_opt`/`sfr_xch_opt`.

**The check only masks the return path; the secret is already fetched.** `rrc.sv:555-561`:
```
2'h1: ahbarray.hrdata = cmd_user_read_dis ? 64'h0 : ahb_rd_buf[127 : 64];
...
default: ahbarray.hrdata = cmd_user_read_dis ? 64'h0 : ahb_rd_buf[63:0];
...
`theregfull(clktop, coreresetn, ahb_rd_buf, '0) <= trc_dout_ready_done ? {trc_dout_s1[127:0],trc_dout_s0[127:0]} : ahb_rd_buf;
```
`rrc.sv:373` starts the array read before the decision:
```
assign ahb_read_acram = ahb_array_trans & ahbarray.hsel & (keysel_ahb | datasel_ahb);
```
`cmd_user_read_dis` (`rrc.sv:828`) is a single combinational term gating a data mux, with no redundancy. `rrc.sv:846` shows the read FSM transition does **not** consult `cmd_user_read_dis` (only writes do, at `rrc.sv:850,853`).

`trustkey` source: `soc_coresub.sv:836` `.trustkey(truststate)`, where `truststate` is `logic [255:0]` (`soc_coresub.sv:503`) but the SCE drives only 128 bits (`sce.sv:53`, `TSC=128`). Bits `[255:128]` are unconnected → key slots with `akeyid ≥ 128` are permanently locked out.

### 2.8 Truststate — the ReRAM key unlock bits

`sce_sec.sv:113-123`:
```
logic [TSC-2:0] tsreg;
generate
    for (genvar i = 0; i < TSC-1; i++) begin
    `theregrn( tsreg[i] ) <= ((hmac_kid==i)&mode_sec & hmac_pass) ? 'b1 : ((hmac_kid==i)&mode_sec & hmac_fail) ? 'b0 : tsreg[i];
    end
endgenerate
    // the MSB is always 1.
assign ts = { 1'b1, tsreg };
```
- `hmac_kid = kid` from `combohasha.sv:221` `apb_cr #(.A('h60), .DW(10)) sfr_keyidx` — the slot index being unlocked is a plain software register.
- `truststate[127]` is hard-wired 1 → ReRAM key slot with `akeyid == 127` is always "trusted".
- The trust bits are readable over APB: `sce_glbsfra.sv:103` `apb_sr #(.A('he0), .DW(32), .SFRCNT(TSC/32)) sfr_ts`.
- **`sce_ts` is reset by system `resetn`, not `sceresetn`** — `sce.sv:294-304` passes `.resetn` (system) while `sce_sec` at `sce.sv:275` gets `.resetn(sceresetn)`. Trust bits therefore survive `ar_reset`, `ar_clrram`, and mode quit.

The comparison that sets them, `combohasha.sv:483-490`:
```
`theregrn( chkprepass ) <=  ~mfsmcheckscrt ? '0 :
                            mfsmtog & mfsmcheckscrt ? '1 :
                            schxwpreq.segwr | chnli_wpreq.segwr ? chkprepass && ( chnlscrt_wpreq.segwdat == '0 ) : chkprepass;

`theregrn( chkdone ) <= mfsmcheckscrt & (schdonex|chnli_done) ;
assign chkpass = chkdone && chkprepass;
assign chkfail = chkdone && ~chkprepass;

`theregrn( hmac_pass ) <= chkpass;
`theregrn( hmac_fail ) <= chkfail;
```
`chkprepass` is seeded to `'1` and only ever falsified on cycles where a write strobe is present. If the compare channel completes with zero write strobes, the comparison passes vacuously. The compare source is `schcrx.axstart = PM_KS_BA + kid * ( 256/8 )` (`combohasha.sv:463`) with `schcrx.transize = STSIZE` derived from `cr_func` (`combohasha.sv:525-529`).

### 2.9 Redundancy/BIST readback path (all crypto RAMs)

`rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:94-138` (`rbspmux`, used by every `cryptoram` at `cryptoram.sv:146-164`, by `aoram.sv:148-166`, and `rbdpmux` by `mimm_dpram.sv:96`):
```
logic rb_clk_undft; CLKCELL_MUX2 c1 (.A(clk), .B(rbs.ramclk), .S(cmsbist), .Z(rb_clk_undft));
...
assign rb_cen  = cmsatpg ? '1 : undft_cen  ; assign undft_cen  = cmsbist ? rbs.ramcen   : cen  ;
assign rb_gwen = cmsatpg ? '1 : undft_gwen ; assign undft_gwen = cmsbist ? rbs.ramgwen  : gwen ;
assign rb_wen  = cmsatpg ? '1 : undft_wen  ; assign undft_wen  = cmsbist ? rbs.ramwen   : wen  ;
assign rb_a    = cmsatpg ? '1 : undft_a    ; assign undft_a    = cmsbist ? rbs.ramaddr  : a    ;
assign rb_d    = cmsatpg ? '1 : undft_d    ; assign undft_d    = cmsbist ? rbs.ramwdata : d    ;
...
assign q            = cmsatpg ? undft_q : rb_q;
assign rbs.ramrdata = cmsatpg ? undft_q : rb_q;
```
Two things: (a) with `cmsbist` asserted, the `rbif` bus fully owns address/clock/enable of every crypto RAM; (b) `rbs.ramrdata` is driven with live RAM read data **unconditionally** — the BIST master sees crypto-RAM reads during normal operation regardless of `cmsbist`.

`cmsbist` origin: `rtl/asic_top/rtl/soc_top.sv:397` `assign cmsbist = cmstest;` (from the `cms` mode controller, `soc_top.sv:379-393`). The BIST master is a JTAG-attached core: `rbist_wrp` takes `jtagif.slave jtagrb` (`rbist_wrp.sv:23`) and instantiates the black-box `rbist rbcore(.*)`; it is connected to `rbif_sce_sceram_10k`, `rbif_sce_hashram_3k`, `rbif_sce_aesram_1k`, `rbif_sce_pkeram_4k[0:1]`, `rbif_sce_aluram_3k[0:1]`, `rbif_sce_mimmdpram`, `rbif_acram2kx64`, `rbif_aoram1kx36[0:1]` (`soc_top.sv:990-1008`). In this A1 RTL the wrapper ties its own drive signals off (`rbist_wrp.sv:246-252` `sce10k_bcen='1; sce10k_bgwen='1; sce10k_ba='0; sce10k_bd='0;`), so the effective control lives in the black-box core inserted at synthesis.

### 2.10 No memory scrambling anywhere

`cryptoram.sv:106-119` instantiates `gnrl_sramc` with:
```
.scmben('0),
.scmbkey('0),
```
Same at `aoram.sv:95` (`.scmben(1'b0)`), `ifram.sv:82`, `core_srambank.try8k.sv:86`, `cm7sys_tcm.sv:116-117`, and `.scmbkey('0)` at `soc_coresub.sv:721,739`, `soc_ifsub.sv:240,253`. Every RAM in the SoC — crypto RAMs, main SRAM, TCMs, AO RAM — stores plaintext with no address/data scrambling.

### 2.11 XIP/QFC flash path is unencrypted

`rtl/modules/core/rtl/qfc_aes.sv:16-74` — the module named `qfc_aes`, instantiated at `rtl/modules/core/rtl/qfc.sv:244`, is a **pure AXI wire-through**:
```
module qfc_aes (
	input logic clk,    // Clock
	input logic resetn, // Clock Enable
	axiif.slave  axis,
	axiif.master axim
);
    assign axim.arvalid =   axis.arvalid ;
    assign axim.araddr =    axis.araddr ;
    ...
    assign axis.rdata =     axim.rdata ;
```
There is no cipher, no key, no integrity check. External SPI/QSPI flash content (T3) reaches the fabric verbatim.

---

## 3. ZEROIZATION STORY

### 3.1 The single clear signal

`sce_sec.sv:79-87`:
```
assign modequit = devmode[1] ? '0 : ~( scemodereg == 0 ) && ~( scemode == scemodereg ) ;

assign sceresetnin = ~( modequit | ar_reset );

`theregrn( initregs ) <= { initregs, 1'b1 };

assign sceramclr = ( initregs == 4'h7 ) | ar_clrram ;
```
`ar_reset` / `ar_clrram` are unlocked APB action registers, `sce_glbsfra.sv:86-87`:
```
apb_ar #(.A('h1c), .AR(32'h5a)) sfr_arrst       (.ar(ar_reset), .*);
apb_ar #(.A('h1c), .AR(32'ha5)) sfr_arclr       (.ar(ar_clrram), .*);
```
i.e. write `0x5a` / `0xa5` to `0x4002_801C`. `sceramclr` fans out to every engine RAM: `sce.sv:424` (SCERAM), `:449` (hash), `:489` (PKE), `:515` (AES), `:556` (ALU).

### 3.2 The clear FSM

`cryptoram.sv:58-78`:
```
assign ramclrdone = ( ramclrfsm == clrend );
`theregrn( ramclrfsm ) <= ramclr ? clrstart :
                          ramclrdone ? '0 : ramclrfsm + ramclren;
`theregrn( ramclren ) <= ramclr ? 1'b1 : ramclrdone ? 1'b0 : ramclren;
assign ramaddr_clr = ramclrfsm;
assign ramen_clr = '1;
assign ramrd_clr = '0;
assign ramwr_clr = '1;
assign ramwdat_clr = '0;
...
assign ramrdat = ramclren ? '0 : ramrdat0;
assign ramready = ramclren ? '1 : ramready0;
```
Defaults: `clrstart = '0`, `clrend = thecfg.WCNT-1` (`cryptoram.sv:24-25`) — full wipe.

### 3.3 Gaps — things that survive

| # | What survives | Evidence |
|---|---|---|
| **Z1** | **SCERAM words 1984–2495 (RNGA + RNGB) are never cleared.** `sce.sv:417` overrides `clrend`: `.clrend (scedma_pkg::SEGADDR_RNGA-1)` — i.e. 1983. TRNG output pooled for key generation persists across `ar_clrram`, `ar_reset`, mode quit, and SCE reset. |
| **Z2** | **MIMM dual-port RAM has no clear at all.** `mimm_dpram.sv:18-32` has no `ramclr` port; `mimm.sv:273,624` instantiate it without one; `sceramclr` never reaches it (`sce.sv:489` passes `ramclr` to `pke`, which forwards only to the two `cryptoram` PRAMs at `pke.sv:1517,1535`). 256×64 bits of Montgomery intermediates survive every software-visible reset. |
| **Z3** | **`sce_memc` FIFO state is on system reset, not SCE reset.** `sce.sv:397` `.resetn (resetn)`. `scedma_simplefifo` pointers/counts (`sce_dmachnl.sv:325-332`) survive `ar_reset` / mode quit. Combined with Z1, the RNGA/RNGB FIFOs and their contents both survive. |
| **Z4** | **SCERAM's own clear FSM is on system reset.** `sce.sv:421` `.resetn(resetn)`, while every other `cryptoram` inherits `sceresetn`. Asymmetric reset domain for the wipe machinery. |
| **Z5** | **Trust state survives.** `sce.sv:298` `.resetn,` (system) on `sce_ts` — `truststate` / ReRAM key unlock bits are unaffected by SCE reset or mode change (§2.8). |
| **Z6** | **No wipe on tamper.** There is no tamper input to `sce_sec`, `cryptoram`, or `sce_glbsfr`; `sceramclr` has exactly two sources (`sce_sec.sv:87`). No sensor/mesh event reaches any zeroization logic. |
| **Z7** | **No wipe on mode entry.** `sceuserlock` fires only on `scemodereg == 0 → nonzero` (`sce_sec.sv:58`) and `modequit` only on `nonzero → different` (`sce_sec.sv:81`). Entering `mode_sec` from `mode_non` performs no clear — data left in SCERAM by the previous non-secure owner is visible to the secure context, and vice-versa for the residue of a `mode_xls` session. |
| **Z8** | **`ahb_rd_buf` in the ReRAM controller is never scrubbed.** `rrc.sv:561` holds the last 256-bit array word (key material) until the next completed read. |
| **Z9** | **Datapath flops.** `sce_dmachnl.sv:158-168` `thedatreg`, `trng.sv:361` `chnlo_rpres.segrdat`, `AesCore` round registers, `data_buf.v` `buf_data`, `lfsr129.v` `lfsr_chain` — none are touched by `ramclr`. |
| **Z10** | **AO domain.** `aobureg` `cr_buregs` and `aoram` are reset only by `porresetn` (`ao_top.sv:224,236`), i.e. only by AO power-on reset. They survive main-domain reset, sleep, brownout of the core rail (T4), and warm reboot. `ret1n` is tied `1'b1` (`ao_top.sv:264`). |
| **Z11** | **Out-of-range AHB reads return stale data.** `scedma_amba.sv:85,92`: `assign ahbs.hready = ahbs_dpvld ? (...) : 1'b1;` and `assign ahbs.hrdata = rpres.segrdat;` with `ahbs_cpvld` gated by `ahbs_segvld` (`:84`). An address ≥ word 2496 (`0x4002_2700`+) never starts a channel, so `hready` is 1 immediately and `hrdata` returns the previous channel's read data with no error. |

---

## 4. CROSS-DOMAIN CROSSINGS

### Clock domains
- **AHB → SCE:** `sce.sv:151-157` `ahb_sync #(.SYNCDOWN(0),.SYNCUP(0)) ahbs_sync` with `.resetn(sceresetn)` — the CDC block itself is held in reset by the SCE reset, while its `hclken` is tied `'1`.
- **Per-engine gated clocks:** `sce.sv:251-259` `ICG uclksub(.CK(clk), .EN(cr_suben[gvi]), .SE(cmsatpg), .CKG(clksub[gvi]))`, `cr_suben` from `sce_glbsfra.sv:79` (`sfr_suben`, IV `0x1f`). Software can freeze an engine's clock mid-operation while its RAM stays on `clk`.
- **PKE double domain:** `pke` runs on `clksub[2]` while its RAMs run on `clkram = clk` (`sce.sv:479-486`); the mask LFSRs run on `clkpke` (`pke.sv:799,804`) reseeded via `sync_pulse` (`pke.sv:795`).
- **TRNG:** entropy is captured on 8 free-running analog clocks and re-synchronized into `clk` — see §5.
- **AO:** `dkpc` keypad events cross `clk32k → pclk` through `udma_dc_fifo` (`dkpc.sv:151-166`); `wkupvld_async` (`dkpc.sv:65,89`) is a raw asynchronous combinational function of the four `kpi[].pi` pads.
- **ReRAM:** `clktop` array domain → `hclk` for error flags via `sync_pulse` (`rrc.sv:830-834`); read data crosses via `ahb_rd_buf` sampled on `clktop` (`rrc.sv:561`) and consumed combinationally on the AHB (`rrc.sv:555-558`).
- **BIST:** `jtagrb.tck → clksys` via `sync_pulse su0` (`rbist_wrp.sv:186`); ReRAM BIST clocks are literally JTAG TCK — `rrc.sv:898-899`:
  ```
  ICG rramicg_tck0 ( .CK (jtag[0].tck ),   .EN ( bist_enable ), .SE('0), .CKG ( rramclk_tck0 ));
  ICG rramicg_tck1 ( .CK (jtag[1].tck ),   .EN ( bist_enable ), .SE('0), .CKG ( rramclk_tck1 ));
  ```
- **IPT JTAG TAP → AO:** `soc_top.sv:947,951` `sync_pulse` from `jtagipt.tck` into `clksysao` / `clksys_undft`.

### Power domains
- AO (`ao_top3`, `rtl/modules/ao/rtl/ao_top.sv`) holds `aobureg`, `aoram` macros, `dkpc`, PMU trim. Isolation is `ao_iso_enable` applied only to the RAM `cen`/`gwen` (`ao_top.sv:251-252`).
- The `aoram` **controller** (`aoram.sv`) lives in the main domain in `soc_coresub`, while the **macros** live in AO (`ao_top.sv:248`), with `aoram_clkb/bcen/bwen/bd/ba/bq` crossing the domain boundary as raw SRAM pins.

### Module boundaries carrying secrets
- `sce` → fabric: `axim[0:1]` (`sce.sv:51`), AXIDs `SCEA=5` / `SCES=6` (`scedma.sv:193,239`). `rrc.sv:668` collapses both into one `scesel`.
- `sce` → `rrc`: `sceuser` (`soc_coresub.sv:837`) and `truststate` (`soc_coresub.sv:836`).
- `sce` → pads: `iptorndlf`, `iptorndhf` (§5).
- All crypto RAMs → `rbist`: `rbif_sce_*` (§2.9).

---

## 5. TRNG ENTROPY PATH, END TO END

```
ana_rng_0p1u ─► RNG_CELL (8 ring oscs)  ─► rngclklfpre[7:0] ─ICG─► rngclklf[7:0]   (8 sampling clocks)
OSC_32M ─► rngclkhf ─► 128-stage RNGCELL_BUF chain ─► XOR-tap ─► rngclkhfxor       (sampled datum)
   └► 8 × flop( clk=rngclklf[i], d=rngclkhfxor ) ─► t_rngsrc_dat[7:0] = rngsrc_dat
        ─► digitalization ─► digi_data_out / digi_data_vld (serial bit stream)
             ├► healthtest        (repetition count, status only)
             ├► data_buf          (buf_data[255:0]  ◄── APB READABLE)
             └► postprocess ──► lfsr129 | ctr_aes ──► rngcore_dataout[127:0]
                                                       └► scedma_chnl ─► SCERAM RNGA / RNGB
```

### 5.1 Raw source
`trng.sv:194-212` — `RNG_CELL osclf` (8 outputs, `SEL`/`EN` from SFR) and `OSC_32M oschf` (`CFG` from SFR). Config register `trng.sv:108,131`:
```
apb_cr #(.A('h00), .DW(13) )      sfr_crsrc       (.cr(cr_src), .prdata32(),.*);
...
assign { chaincut, rnghf_cfg[6:0], rnglf_sel[2:0], rnghf_en, rnglf_en } = cr_src;
```
Buffer chain and its per-tap enable mask, `trng.sv:216-228`:
```
assign rngchain0[0] = cmsatpg ? 1'b0 : rngclkhf;
assign rngchain1[0] = cmsatpg ? 1'b0 : ~chaincut & rngchain0[CHAINW/2];
...
assign rngclkhfxor = ^( {rngchain0[CHAINW/2:1],rngchain1[CHAINW/2:1]} & rngchainen[CHAINW-1:0] );
```
`rngchainen` is a 128-bit software register (`trng.sv:120` `sfr_chain` at offset `0x40`), reset to 0 → **all taps masked → `rngclkhfxor = 0`** until software programs it.

Test overrides, `trng.sv:187-191`:
```
assign cmstest = cmsbist;
assign t_rnglf_sel = cmsatpg ? '0 : cmstest ? '1 : rnglf_sel;
assign t_rnglf_en =  cmsatpg ? '0 : cmstest ? '1 : rnglf_en;
assign t_rnghf_en =  cmsatpg ? '0 : cmstest ? '1 : rnghf_en;
assign t_rnghf_cfg = cmsatpg ? 7'b0100110 : cmstest ? ipt_rngcfg : rnghf_cfg;
```
and `trng.sv:251`:
```
assign rngsrc_dat = cmsatpg ? ~{ t_rnglf_sel, t_rnglf_en, t_rnghf_en, t_rnghf_cfg} : t_rngsrc_dat;
```
With `cmsatpg` the entropy source becomes a **constant** and the sampling clocks become `clk` (`trng.sv:214,232`). With `cmsbist`, the HF oscillator config comes from the external `ipt_rngcfg` pins (`sce.sv:46`).

**Raw oscillator observable off-chip.** `trng.sv:248-249`:
```
`theregfull( rngclkhf, sysresetn, iptorndhf, '0 ) <= ( rngclkhftestfdcnt == 9 ) ? cmstest ^ iptorndhf : iptorndhf;
assign iptorndlf = rngclklfpre[0];
```
`iptorndlf` is the *undivided, ungated* LF ring-oscillator output. Route to pins, `rtl/asic_top/rtl/soc_top.sv:940-945`:
```
assign iptpo[0:5] =
      iptposel == 0 ? 'h2a :
      iptposel == 1 ? ao_iptpo[0:5] :
      iptposel == 2 ? { VD09L, VD09H, VD25L, VD25H, VD33L, VD33H } :
      iptposel == 3 ? { iptorndlf, iptorndhf, iptpopll, iptporng, iptpoosc } :
                      'h15;
```
`iptposel = iptregout[4][11:8]` (`soc_top.sv:934`) is a JTAG TAP register, enabled by `soc_top.sv:907` `assign iptap_en = cmstest | cmsbist | cmsatpg;`.

### 5.2 Digitalization
`rtl/modules/crypto_trng/rtl/digitalization.v:55-61` — each of 8 channels samples on its own async ring clock:
```
always @(posedge clk_ana[i] or negedge rstn)begin
    if(!rstn)  data_samp[i] <= 1'b0;
    else       data_samp[i] <= data_samp_pre[i];
end
assign data_samp_pre[i]=ana_vld[i]?ana_data[i]:data_samp[i];
```
Two-flop resync of the ring clock only (`:70-75`); `data_samp` itself crosses from `clk_ana[i]` to `clk` with **no synchronizer**. Optional parity (XOR-of-8) folding, `digitalization.v:81`:
```
assign digi_data_out_tmp_pre[0]           = partityfilter_en ? (^data_samp[ANA_NUM-1:0]): data_samp[0];
```
Channel enables `ana_en`/`ana_vld` come from `cr_ana` (`trng.sv:109,132`) — software can enable a single channel and disable the parity filter, reducing the source to one raw ring.

### 5.3 Health test
`rtl/modules/crypto_trng/rtl/healthtest.v:33-39` — entire test:
```
assign digi_data_save_pre = digi_data_vld ? digi_data_out :digi_data_save;
assign healthtest_cnt_pre = (~healthtest_en) ? 6'h0 : 
	                    (digi_data_vld&(digi_data_out==digi_data_save)&(healthtest_cnt< healthtest_length))? healthtest_cnt+1'b1:
		    (digi_data_vld&(digi_data_out!=digi_data_save))? 6'h0 :healthtest_cnt;

assign healthtest_err_pre = (digi_data_vld&(digi_data_out==digi_data_save)&(healthtest_cnt>=healthtest_length))? 1'b1:
	                    (digi_data_vld&(digi_data_out!=digi_data_save))? 1'b0 :healthtest_err;   
```
Properties: repetition-count only (no adaptive-proportion, no startup test); `healthtest_err` is **non-sticky** — cleared by a single bit toggle; `healthtest_en` and `healthtest_length` are software (`trng.sv:263,306,309`); and **`healthtest_err` gates nothing.** In `rng_top.v:79-87` it is only an output; in `trng.sv:268-271,124` it feeds a saturating counter and a status/flag bit:
```
`theregrn( sr_hlthtest_errcnt ) <= ar_start ? '0 : sr_hlthtest_errcnt + sr_hlthtest_errrise;
`theregrn( hlthtest_errof ) <= ( sr_hlthtest_errcnt == '1);
```
Nothing in the path from `digi_data_out` to `rngcore_dataout` to `chnlo_start` (`trng.sv:357`) consults it.

### 5.4 Conditioning buffer — the raw-entropy leak
`rtl/modules/crypto_trng/rtl/data_buf.v:78-98`:
```
    else if((~trng_drng_sel)&digi_data_vld)begin 
        buf_data_pre[255:0] = {buf_data[254:0],digi_data_out};
    end
...
//data output
always @(*)begin
    case(buf_addr)
         3'd7   :buf_dataout=buf_data[31 :  0]; 	
         ...
         3'd0   :buf_dataout=buf_data[255:224];
	 default:buf_dataout=buf_data[255:224];
   endcase
end
```
`buf_data` is the shift register of **unconditioned digitized entropy bits** and simultaneously the DRBG seed. It is wired to a plain APB window, `trng.sv:278`:
```
apb_buf  #(.BAW(3), .A(12'h30), .DW(32) ) sfr_buf (.prdata32(),.*);
```
→ reading `0x4002_E030`..`0x4002_E03C` returns the raw pre-conditioning entropy / current seed word by word (`apb_buf`, `trng.sv:409-445`, auto-incrementing `buf_addr`). Writing the same window (with `trng_drng_sel=1`) **installs an attacker-chosen 256-bit seed** (`data_buf.v:68-77`).

`trng_drng_sel = cr_drng_en` and `postprocess_opt = cr_postproc_opt` both come from one unlocked SFR, `trng.sv:110,257-264`:
```
apb_cr #(.A('h08), .DW(17) )      sfr_pp          (.cr(cr_postproc), .prdata32(),.*);
...
assign { cr_reseed_sel, cr_reseed_intval[1:0], cr_gen_intval[1:0], cr_healthtest_len[5:0],
         cr_postproc_opt[1:0], cr_drng_en, cr_hlthtest_en, cr_pfilter_en, cr_gen_en } = cr_postproc;
```
`sfrlock` in this module is hard-tied 0: `trng.sv:52` `` `theregrn( sfrlock ) <= '0; ``.

### 5.5 Post-processing
`rtl/modules/crypto_trng/rtl/postprocess.v:156-159`:
```
assign rngcore_dataout    =(postprocess_opt==2'd0)? lfsr_dataout[127:0]  :
           	           (postprocess_opt==2'd1) & (~aes_flag) ? aes_text_out[255:128]:
           	           (postprocess_opt==2'd1) &   aes_flag  ? aes_text_out[127:0]  :
		                                                             ctr_dataout[127:0]   ;
```
- **opt 0 = bare LFSR.** `lfsr129.v:100` `assign lfsr_dataout = lfsr_chain[127:0];` — 128 of the 129 state bits emitted directly. Two consecutive outputs over-determine the state, so all past/future output is recoverable. Fixed reset/degenerate state, `lfsr129.v:66,88`:
  ```
  lfsr_chain        <= 129'h1_A39A8864_5DF3BECE_074EC5D3_BAF39D18;
  ...
  assign lfsr_chain_pre   = (|lfsr_chain==1'b0) ? 129'h1_A39A8864_5DF3BECE_074EC5D3_BAF39D18: ...
  ```
  In TRNG mode raw entropy is only XOR-folded one bit per shift (`lfsr129.v:91`): `{lfsr_chain[127:0],lfsr_out^digi_data_out}`.
- **opt 1 = single AES call with software-supplied key**, `postprocess.v:179-182`:
  ```
  assign aes_key_sel        =(postprocess_opt==2'd1)? buf_data[255:128]    : aes_key_ctr;
  assign aes_text_in_sel    =(postprocess_opt==2'd1)? buf_data[127:0]      : aes_text_in_ctr;
  ```
- **opt 2 = CTR_DRBG** (`ctr_aes.v`), with `personalization_string` / `additional_input_*` from `apb_shfin` SFRs at `0x20/0x24/0x28` (`trng.sv:275-277`).

### 5.6 Consumer
`trng.sv:341-368` — the 128-bit result is pushed by a `scedma_chnl` into SCERAM:
```
assign rngcore_data = rngcore_data128;
...
assign chnlo_start = rngcore_en & rngcore_dataout_vld & ~chnlo_busy ;
...
`theregrn( chnlo_rpres.segrdat ) <= rngcore_data[chnlo_rpreq.segptr[1:0]];
...
assign chnlo_cfg.wpsegcfg = ~opt_segsel ? scedma_pkg::SEG_RNGA : scedma_pkg::SEG_RNGB;
assign chnlo_cfg.transsize = 4;
```
`opt_segsel` from `sfr_opt` at `0x0c` (`trng.sv:111,133`). RNGA/RNGB are bus-readable in every mode per `8'b10_11_10_10` (`scedma_pkg.sv:308-309`), and are the two segments the wipe skips (§3.3 Z1).

The TRNG block also runs entirely on the **system** reset, not the SCE reset — `sce.sv:531-535` passes `.resetn(resetn), .sysresetn(sysresetn)`, so `rngcore_en`, `rngcnt`, `sr_hlthtest_errcnt` and `buf_data` are untouched by SCE reset / mode quit.

---

## 6. SIDE-CHANNEL COUNTERMEASURE STATE (AES / PKE masking)

`aes.sv:282-283`:
```
drng_lfsr #( .LFSR_W(229),.LFSR_NODE({ 10'd228, 10'd225, 10'd219 }), .LFSR_OW(32), .LFSR_IW(32), .LFSR_IV('h5a5a_a5a5) )
    ua( .clk(clk), .sen('1), .resetn(sysresetn), .swr(maskseedupd), .sdin(maskseed), .sdout(aesmaskdat) );
```
feeding `AesCore .MaskIn(aesmaskdat)` (`aes.sv:273`).

`rtl/modules/common/rtl/insauth.v:38`:
```
`theregfull( clk, resetn, sdata, LFSR_IV ) <= sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata ;
```
The reseed path XORs **`sdin[31]` alone** — one bit, zero-extended against a 229-bit state. Writing the 32-bit `maskseed` SFR (`aes.sv:154-155`, `0x4002_D020` / action `0x4002_D024`) injects exactly one bit of entropy. With a fixed compile-time `LFSR_IV` and `sen` tied `'1`, the AES mask sequence is fully deterministic from reset.

PKE, `pke.sv:788-805`:
```
`theregfull( clkpke, resetn, optsec0, '0 ) <= mimmcr[3];
...
assign mimm_dbrnd = optsec ? pkemaskdat : '0;
...
drng_lfsr #( ... .LFSR_IV('h5a5a_a5a5) ) ua( .clk(clkpke), .sen(optsec), ... .sdout(pkemaskdat[31:0]) );
drng_lfsr #( ... .LFSR_IV('ha5a5_5a5a) ) ub( .clk(clkpke), .sen(optsec), .swr(maskseedupd_sync), .sdin(pkemaskdat[31:0]), .sdout(pkemaskdat[63:32]) );
```
`mimmcr` is an unlocked SFR (`pke.sv:310`) resetting to 0, so **PKE masking is off by default** and, when off, the LFSRs are also frozen (`sen(optsec)`), so re-enabling it starts from a known state.

Dangling port: `sce.sv:507-508,524` drives `aesmask = '0` into `aes.maskin`, but `maskin` (`aes.sv:35`) is never referenced inside `aes.sv`.

---

## 7. GLOBAL SECURITY-DISABLE LEVERS (read these before filing anything)

`rtl/modules/crypto_top/rtl/sce.sv:131-139`:
```
assign devmode_sce = devmode ? '1 : nvrcfg[28];// != 8'h00) || devmode;
    // [0] for ahben bypass
    // [1] for mode quit reset bypass
    // [2] for mode value lock bypass
    // [3] pke ahbs lock bypass
    // [4] alu sec bypass

assign pkeahbslock = devmode_sce[3] ? '0 : mode_sec;
assign alusec = devmode_sce[4] ? '0 : mode_sec;
```
`nvrcfg = nvrcfgdata.cfgsce` (`soc_coresub.sv:545`) = ReRAM NVR config word 10 (`nvrcfgs.sv:125`). Byte 28 individually disables the SCE bus gate, the mode-quit reset (and hence the RAM wipe), the mode lock, the PKE RAM lock, and the ALU key guard. Byte 29 == `0x5a` replaces the entire DMA access-control table with NVR contents (`scedma_ac.sv:40,66`).

`devmode` itself: `soc_coresub.sv:509` `assign scedevmode = cm7cfg_dev|vexcfg_dev;` from `soc_coresub.sv:271`:
```
`theregfull( hclk, resetn, corecfg_devreg , '0 ) <= ( nvrcfgdata.cfgcore.devena     == nvrcfg_pkg::cpudevmode );
```
A single non-redundant 32-bit magic compare (`cpudevmode = 32'h298ca435`, `nvrcfgs.sv:82`) unlocks **all five** SCE bypasses simultaneously. On the FPGA build only, `brc.sv:120` `assign nvrcfgdata = nvrcfg_pkg::defnvrcfg;` and `nvrcfgs.sv:87` sets `devena : cpudevmode` — devmode is on by default in that build. In the ASIC build `nvrcfgdata = syscfgdata` (`brc.sv:130`), a register array reset to 0, so devmode is off until ReRAM boot-read supplies the magic.

**Undriven security control:** `rtl/modules/crypto_top/rtl/sce_glbsfra.sv:63-68`:
```
    logic apbrd, apbwr;
    logic pclk;
    logic sfrlock;
    assign pclk = clk;

//    `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;
```
`sfrlock` is declared and never assigned, yet is bound by `.*` into every SFR in the SCE global register file (`sce_glbsfra.sv:78-103`) including `sfr_arrst` and `sfr_arclr`. Compare with the modules that do drive it: `dkpc.sv:181-182`, `aobureg.sv:28-30`, `scedma.sv:82,91`, `rbist_wrp.sv:166-168`, `trng.sv:52`, and the operational lock in `aes.sv:135` / `combohasha.sv:159`:
```
`theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;
```

`rrc.sv:274-286` — every ReRAM controller SFR, including the suicide/erase action register, is instantiated with `.sfrlock(1'b0)`:
```
apb_ar #(.A('hF0), .AR(PM_RRAM_SUICIDE))    sfr_rrcar       (.ar(rrcar_suicide), .resetn(coreresetn), .sfrlock(1'b0), .*);
```

---

## 8. QUICK INDEX FOR DOWNSTREAM FINDERS

| Theme | Start here |
|---|---|
| SCERAM address escape / AC bypass | `sce_dmachnl.sv:123-129`, `sce_memc.sv:212`, `scedma_ac.sv:45-47`, `scedma.sv:113-116` |
| Mode-transition residue | `sce_sec.sv:58,81,87`, `sce.sv:417` |
| MIMM / never-zeroized state | `mimm_dpram.sv:18-32`, `mimm.sv:273,624` |
| Owner-latch race | `sce_sec.sv:58-64,70-77` |
| ReRAM key readout | `rrc.sv:373,555-561,712-720,827-828` |
| Trust-state unlock | `combohasha.sv:462-490`, `sce_sec.sv:113-123`, `sce.sv:294-304` |
| NVR / devmode kill-switch | `sce.sv:131-139`, `soc_coresub.sv:271,509`, `scedma_ac.sv:40,66` |
| TRNG seed exposure & forcing | `trng.sv:278,52,257-264`, `data_buf.v:68-98` |
| TRNG health test | `healthtest.v:33-39`, `trng.sv:268-271` |
| LFSR-only "random" | `lfsr129.v:66,88-100`, `postprocess.v:156` |
| Raw entropy on pins | `trng.sv:248-249`, `soc_top.sv:907,940-945` |
| DPA mask determinism | `insauth.v:38`, `aes.sv:282-283`, `pke.sv:788-805` |
| BIST/JTAG RAM readback | `ram_1rw_s.sv:94-138`, `rbist_wrp.sv`, `soc_top.sv:397,990-1008`, `rrc.sv:898-899` |
| No scrambling / cold boot | `cryptoram.sv:112-113`, `aoram.sv:95`, `soc_coresub.sv:721,739` |
| Unencrypted XIP flash | `qfc_aes.sv:16-74`, `qfc.sv:244` |
| AO persistence | `aobureg.sv:26-35`, `ao_top.sv:224,236,248-266` |
| PIN/keypad side channel | `dkpc.sv:89,142,151-166,198-205` |
| Undriven `sfrlock` | `sce_glbsfra.sv:65,68` |