# BAOCHIP-1X — TRUST BOUNDARY & ACCESS-CONTROL MAP

All paths below are relative to the repository root. Line numbers verified by direct read.

**Black boxes (not in this repo — cannot be verified, treat as unknown):** `nic400_1` (ARM NIC-400, instantiated `rtl/modules/bmxcore/rtl/nic1_intf.sv:117`), `ahb_bmx33_intf` (`rtl/modules/bmxcore/rtl/bmxcore.sv:276`), `ahb_bmxif_intf` (`rtl/modules/ifsub/rtl/soc_ifsub.sv:117`), `CM7AAB` AXI→AHB bridge (`rtl/modules/amba/rtl/aab_intf.sv:37`), `cm7top`, `sdvt_spi_master_core` (`rtl/modules/core/rtl/qfc.sv:268`), `trbcx1r32_daric_wrapper` internals. **hauser/AxUSER propagation through the two AHB bus matrices and through CM7AAB is asserted by the integration but is not provable from open RTL.**

---

## 1. THE PRIVILEGE / IDENTITY SCHEME ("coreuser")

### 1.1 Two orthogonal identity channels

The SoC uses **two separate, weakly-coupled** identity mechanisms:

| Channel | Width | Carried on | Meaning |
|---|---|---|---|
| **AMBAID / `hauser` / `aruser`/`awuser`** | 4 bits (`UW(4)` on AHB, 8 on AXI) | in-band on the bus | *which master* issued the transfer |
| **`coreuser`** | 8 bits (`PM_COREUSERCNT = daric_cfg::CODEMEMCNT + RERAMUSERCNT = 4 + 4 = 8`, `rtl/modules/soc_coresub/rtl/soc_coresub.sv:234-235`) | **sideband wires**, NOT on the bus | *which code region* the CPU is currently executing from |

`coreuser` is **never** attached to a bus transaction. It is routed as a continuous sideband bundle from each CPU to the two consumers (RRC and SCE). The consumer uses `hauser` to *select which* `coreuser` bundle to apply, and samples that bundle **at the time the consumer latches the transfer**, not at the time the master issued it.

### 1.2 AMBAID assignment (the "who am I" tag)

`rtl/asic_top/rtl/daric_cfg_pkg.sv:72-84`:
```
    localparam bit [3:0] AMBAID4_CM7A = 4'h2;   // CM7 AXI master
    localparam bit [3:0] AMBAID4_VEXI = 4'h3;   // Vex instruction AXI
    localparam bit [3:0] AMBAID4_VEXD = 4'h4;   // Vex data AXI
    localparam bit [3:0] AMBAID4_SCEA = 4'h5;   // SCE "general" AXI
    localparam bit [3:0] AMBAID4_SCES = 4'h6;   // SCE "secure" AXI
    localparam bit [3:0] AMBAID4_MDMA = 4'h7;   // MDMA AHB
    localparam bit [3:0] AMBAID4_CM7P = 4'h8;   // CM7 AHB peripheral port
    localparam bit [3:0] AMBAID4_CM7D = 4'h9;   // (unused in RTL)
    localparam bit [3:0] AMBAID4_VEXP = 4'hD;   // Vex AHB peripheral port
    localparam bit [3:0] AMBAID4_UDMA = 4'hA;
    localparam bit [3:0] AMBAID4_UDCA = 4'hB;
    localparam bit [3:0] AMBAID4_SDDC = 4'hC;
```

Where each ID is *driven* (this is the full list of ID sources in the design):

| Master | Driver site | Value driven |
|---|---|---|
| CM7 AXI (`cm7_axim`) | `rtl/modules/core/rtl/cm7sys.sv:670-671` `assign axim.aruser = AXIMID4 \| '0;` | `0x2` |
| CM7 AHB-P (`cm7_ahbp`) | `rtl/modules/core/rtl/cm7sys.sv:695` `assign ahbp0.hauser = AHBPID4;` | `0x8` |
| Vex I-AXI | `rtl/modules/core/rtl/vexsys.sv:191-192` | `0x3` |
| Vex D-AXI | `rtl/modules/core/rtl/vexsys.sv:193-194` | `0x4` |
| Vex AHB-P (`vex_ahbp`) | `rtl/modules/core/rtl/vexsys.sv:166,178` `assign paxim.aruser = AHBPID4 \| '0;` | **`0xD`** |
| SCE general DMA `axim[0]` | `rtl/modules/crypto_top/rtl/scedma_amba.sv:395,412` `assign axim.aruser = PM_AXID \| '0;` with `PM_AXID=AXID` (`scedma.sv:239`) | `0x5` |
| SCE secure DMA `axim[1]` | same module, `PM_AXID = AXID+1` (`rtl/modules/crypto_top/rtl/scedma.sv:193`) | `0x6` |
| MDMA AHB | `rtl/modules/core/rtl/mdma.sv:82` `assign ahbm.hauser = AHBMID4 \|'0;` | `0x7` |
| **BDMA (BIO) AXI mem master** | `rtl/modules/bio_bdma/rtl/bio_bdma.sv:1360,1373` `assign axim.aruser = AHBMID4\|'0;` with default `parameter AHBMID4 = daric_cfg::AMBAID4_MDMA` (`bio_bdma.sv:122`), instantiated with **no override** (`rtl/modules/ifsub/rtl/soc_ifsub.sv:344` `bio_bdma #() bio (`) | **`0x7` — collides with MDMA** |
| **BDMA (BIO) AHB peri master** | `rtl/modules/bio_bdma/rtl/bio_bdma.sv:1580` and `:1670` `assign ahbm.hauser = '0;` | **`0x0`** |
| uDMA AXI | `rtl/modules/ifsub/rtl/ifsub1_intf.sv:178-179` | `0xA` |
| USB device (udc) | `rtl/modules/ifsub/rtl/udc.sv:323,327` | `0xB` |
| SDDC | `rtl/modules/ifsub/rtl/sddc.sv:188` `assign ahbm.hauser = '0;` (instance is commented out, `soc_ifsub.sv:307-327`) | `0x0` |

AXI→AHB translation of the tag: `rtl/modules/amba/rtl/aab_intf.sv:54,67,116,120`
```
/*[15:0]   */.AWUSER         (axislave.awuser|16'h0),
/*[15:0]   */.ARUSER         (axislave.aruser|16'h0),
  assign ahbmaster.hauser = uaab.HAUSER;
  assign ahbmaster.hmaster = ahbmaster.hauser;
```
AHB demux/mux propagate it unchanged: `rtl/modules/amba/rtl/ahb_demux.sv:114`, `rtl/modules/amba/rtl/amba_components.sv:275, 426, 868, 1022`.

**Note the one place the tag is manufactured rather than forwarded:** `rtl/modules/amba/rtl/ahb_axi_bdg.sv:34,40`
```
    assign axim.awuser = ahbs.hmaster | 8'h0;
    assign axim.aruser = ahbs.hmaster | 8'h0;
```
(used for the MDMA AHB→AXI path in `bmxcore.sv:180-188`), i.e. AXI user is re-derived from AHB `hmaster`.

### 1.3 `coreuser` bit semantics

Documented in `rtl/modules/rrc/rtl/rrc.sv:642`:
```
  //    coreuser    [7]:fw1,    [6]:fw0,            [5]:boot1           [4]:boot0
```
Bits `[3:0]` mirror `code_mem_map` (itcm/dtcm/reram/sram) for the CM7 and are a bit-reversed copy of `[7:4]` for the Vex.

### 1.4 CM7 `coreuser` generation — PC-range comparator + debounce

`rtl/modules/soc_coresub/rtl/soc_coresub.sv:247-253` builds the map from ReRAM config:
```
    assign coreusermap_cm7[PM_COREUSERCNT-1:daric_cfg::CODEMEMCNT] = '{
        '{idx: 32'd7 , start_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_fw1_start),   end_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_fw1_end)    }, // fw1
        '{idx: 32'd6 , start_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_fw0_start),   end_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_fw1_start)  }, // fw0
        '{idx: 32'd5 , start_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_boot1_start), end_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_fw0_start)  }, // boot1
        '{idx: 32'd4 , start_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_boot0_start), end_addr: `ambarrb(nvrcfgdata.cfgrrsub.m7_boot1_start)}  // boot0
    };
```
`` `ambarrb(x) = { 10'b0110_0000_00, x, 14'h0 } `` (`rtl/modules/sysctrl/rtl/nvrcfgs.sv:182`) — 16 KB granularity in the 0x6000_0000 ReRAM window.

Generation, `rtl/modules/core/rtl/cm7sys.sv:729-776`:
```
735:    assign corecm7pc[31:0]  = pcptr;
754:        for( gvi = 1; gvi < PM_COREUSERCNT; gvi++ ) begin: GENCOREUSER
755:            assign coreuserreg0pre[PM_COREUSERCNT-gvi-1] = ( corecm7pc >= coreusermap[gvi].start_addr) & ( corecm7pc < coreusermap[gvi].end_addr);
761:    assign coreuserreg0pre[7] = ~|coreuserreg0pre[6:4];
763:    `theregrn( coreuserreg0 ) <= coreuserreg0pre;
769:    `theregrn( coreuserreg1 ) <= coreuserreg0;
770:    assign coreuser_change = ~(coreuserreg1==coreuserreg0);
772:    `theregrn( coreuser_keepcnt ) <= coreuser_change ? '0 : ~coreuser_keep ? coreuser_keepcnt + 1 : coreuser_keepcnt;
773:    `theregrn( coreuser_keep ) <= coreuser_change ? '0 : coreuser_keepcnthit ? '1 : coreuser_keep;
774:    assign coreuser_keepcnthit = (coreuser_keepcnt == coreuser_filtercyc);
776:    `theregrn(coreuser) <= coreuser_keepcnthit ? coreuserreg0 : coreuser;
```
Key properties for finders:
* Line 761 — **any PC not in boot0/boot1/fw0 is classified as `fw1` (bit 7)**, including PC in TCM/SRAM/QSPI/undefined space. `coreuserreg0pre[3:0]` is only driven for `gvi=1..3`, so `coreuserreg0pre[3]` (idx 0 / itcm) is **never assigned** → dangling.
* Line 776 — the exported `coreuser` only updates on the **exact cycle** `coreuser_keepcnthit` is true. `coreuser_filtercyc` comes from ReRAM (`soc_coresub.sv:274`, reset `'0`; ReRAM default `8'h7`, `nvrcfgs.sv:92`). This is a *debounce*, i.e. `coreuser` **lags the PC by up to `filtercyc+2` cycles** — a stale-identity window on every region transition, in **both** directions.
* Clock/reset: `theregrn` → `clk`=`fclk_cm7`, `resetn`=`sysresetn_cm7` (`soc_coresub.sv:307,336,340`). Reset value `'0` — i.e. **`coreuser == 8'h00` (no region) during and immediately after reset**.
* `coreuser` crosses from `fclk` (CM7 clock) into `clktop` (RRC) and `clksce` with **no synchronizer** (see 1.6).

### 1.5 Vex `coreuser` generation — SATP.ASID lookup table (software-programmed)

`rtl/modules/vexriscv/rtl/cram_axi.sv:5814-5849` — an 8-entry LUT comparing `cramsoc_satp_asid` against `coreuser_lut01..71`, producing a 2-bit user, defaulting to `coreuser_user_default`. Then `:5850-5882` one-hot expands to 4 bits, and `:20921-20922`:
```
    coreuser_vex[7:4] <= coreuser_coreuser_4bit;
    coreuser_vex[3:0] <= {coreuser_coreuser_4bit[0], coreuser_coreuser_4bit[1], coreuser_coreuser_4bit[2], coreuser_coreuser_4bit[3]};
```
Machine-mode flag `:20923-20927`:
```
    if (coreuser_enable1) begin
        vex_mm <= ((cramsoc_privilege[0] | cramsoc_privilege[1]) ^ coreuser_invert_priv1);
    end else begin
        vex_mm <= default_mm;
    end
```
CSR bank (`:13177-13206`): `control` (enable, invert_priv), `map_lo`/`map_hi` (8× ASID), `uservalue` (8× 2-bit + default), **`protect`** (the lock). The lock: `:22889-22895`
```
fdre_cosim fdre_cosim(
	.C(sys_clk), .CE(coreuser_protect_storage), .D(1'd1), .R(sys_rst), .Q(coreuser_protect));
```
and `:20878-20918` — while `coreuser_protect` is 1 the shadow registers hold; while 0 they track the CSRs.
* **`coreuser_protect` is cleared by `sys_rst`**, and `sys_rst = ~resetn_vex = ~(cmsatpg ? 1 : coreresetn & vexcfg_en)` (`soc_coresub.sv:311`, `vexsys.sv:233`). Any `coreresetn` (including the software `sfr_rcurst1` write, §4) unlocks the whole coreuser configuration.
* `default_user`/`default_mm` come from ReRAM: `soc_coresub.sv:276-277` ← `nvrcfgdata.cfgrrsub.rv_def_mm` / `.rv_def_user`; ReRAM default is `rv_def_mm : '1` (machine mode!), `rv_def_user : '0` (`rtl/modules/sysctrl/rtl/nvrcfgs.sv:69-70`).
* If `coreuser_enable1 == 0` (reset state), `vex_mm = default_mm` and the coreuser is `default_user` — i.e. **identity is a static ReRAM constant, independent of actual privilege**.

### 1.6 EVERY CHECK SITE for `coreuser` / `hauser` (exhaustive)

There are exactly **two** consumers in the whole design.

#### (A) RRC — ReRAM access control. File `rtl/modules/rrc/rtl/rrc.sv`.

Master identification and coreuser selection:
```
545:    `theregfull(clktop, coreresetn, hauser_reg, '0) <= ahb_array_trans & ahbarray.hsel ? ahbarray.hauser : hauser_reg;
666:    assign cm7sel = ( hauser_reg == AMBAID4_CM7A );
667:    assign vexsel = ( hauser_reg == AMBAID4_VEXI ) | ( hauser_reg == AMBAID4_VEXD );
668:    assign scesel = ( hauser_reg == AMBAID4_SCEA ) | ( hauser_reg == AMBAID4_SCES );
670:    assign coreuser_mux = scesel ? sceuser :
671:                            vexsel ? coreuser_vex : coreuser_cm7;
672:    assign coreuser_in = coreuser_mux;
```
> **`coreuser_mux` has no default branch.** Any master whose `hauser` is not 2/3/4/5/6 (MDMA=7, BDMA-AXI=7, BDMA-AHB=0, uDMA=A, udc=B, sddc=C, or 0) silently inherits **`coreuser_cm7`**, the CM7's live identity.

Other latched request attributes (all in `clktop`, reset `coreresetn`):
```
541:    `theregfull(clktop, coreresetn, haddr_reg, '0) <= ...
546:    `theregfull(clktop, coreresetn, ahb_write_flag, '0) <= ...
547:    `theregfull(clktop, coreresetn, ahb_read_flag, '0) <= ...
660:    `theregfull(clktop, coreresetn, axid_reg, '0) <= axis.arvalid & axis.arready & clken ? axis.arid : axis.awvalid & axis.awready & clken ? axis.awid : axid_reg;
662:    `theregfull(clktop, coreresetn, axprot_reg, '0) <= axis.arvalid & axis.arready & clken ? axis.arprot :
663:                                                        axis.awvalid & & axis.awready & clken ? axis.awprot : axprot_reg;   // note the stray '&'
664:    `theregfull(clktop, coreresetn, vex_mm_reg, '0) <= (axis.arvalid & axis.arready & clken) | (axis.awvalid & axis.awready & clken) ? vex_mm : vex_mm_reg;
676:    assign pri_op = axprot_reg[0];
681:    assign sce_exc_op = axprot_reg[0] & (!mode_sec);
682:    assign sce_sec_op = axprot_reg[0] & mode_sec;
```
Note `axid_reg`/`axprot_reg`/`vex_mm_reg` are latched on the **AXI channel handshake**, while `hauser_reg`/`haddr_reg` are latched on the **AHB phase after the CM7AAB bridge** — different pipeline stages of the same transaction. `coreuser_in` is sampled **combinationally at check time**, i.e. a third, later, point in time.

The five check expressions:
```
712:    assign key_access_error_pre = (((coreuser_in[7:4] & userid_k[7:4])==0) & (ahb_write_flag | ahb_read_flag) |
713:                                ahb_read_flag & ((core_rd_dis_k & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg)) |
714:                                ahb_write_flag & ((core_wr_dis_k & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg)) |
715:                                ahb_read_flag & scesel & (sce_rd_dis_k | (!sce_sec_op) | (keytype_in != keytype_k)) |
716:                                ahb_write_flag & scesel & (sce_wr_dis_k | (!sce_sec_op) | (keytype_in != keytype_k)) |
717:                                (!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))) & data_op & keysel & (userid_k[7:4] != 4'h0);
720:    assign key_access_error = key_access_error_pre;

722:    assign data_access_error_pre = (((coreuser_in[7:4] & userid_k[7:4])==0) & (ahb_write_flag | ahb_read_flag) |     // NOTE: userid_k, not userid_d
...
726:                                ... ) & data_op & datasel & (userid_d[7:4] != 4'h0);
729:    assign data_access_error = data_access_error_pre;

765:    assign rrsub_code_dis = boot0_code_dis & userid_c[0] | boot1_code_dis & userid_c[1] |
766-768                             fw0_code_dis & userid_c[2] | fw1_code_dis & userid_c[3] | rrsub_code_dis_trustkey;
770:    assign code_access_error_inst = rrsub_code_dis_trustkey & ahb_read_flag & (cm7sel|vexsel) & inst_op & codesel;
772:    assign code_access_error_data = (rrsub_code_dis & (cm7sel|vexsel) | ...) & data_op & codesel;
776:    assign code_access_error_pre = (code_access_error_inst |code_access_error_data);
778:    assign code_access_error = code_access_error_pre & rrccr[12];        // <-- gated by a software CR bit

781:    assign info_access_error_pre = (((brdatreg[axi_yadr][255:248] == PM_WRITE_DIS) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel) & ahb_write_flag |
782:                                    ((brdatreg[axi_yadr][247:240] == PM_READ_DIS)  | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel) & ahb_read_flag ) & axi_info & data_op;
785:    assign info_access_error = info_access_error_pre;

815:    assign cfg_prev_dis = (((!(coreuser_in[5] | coreuser_in[4])) & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel)
816:                             & ((haddr_reg[31:14] == PM_CFGD_REGION) | (haddr_reg[31:14] == PM_CFGK_REGION));
818:    assign cfg_access_error_pre = (((cfg_rd_dis & (cm7sel|vexsel)) | cfg_prev_dis) & ahb_read_flag |
819:                                    ((cfg_wr_dis  & (cm7sel|vexsel)) | cfg_prev_dis) & ahb_write_flag ) & data_op;
825:    assign cfg_access_error = cfg_access_error_pre;
```
Enforcement (deny = silent zero, never a bus error):
```
555-558:    2'h1: ahbarray.hrdata = cmd_user_read_dis ? 64'h0 : ahb_rd_buf[127 : 64];  (etc.)
583:    assign ahbarray.hresp = 2'h0;                    // RRC NEVER returns an AHB error
827:    assign cmd_user_write_dis = (key_access_error | data_access_error | info_access_error | code_access_error | cfg_access_error) & ahb_write_flag;
828:    assign cmd_user_read_dis  = (... ) & ahb_read_flag;
850,853:  ( rrcfsm == 0 ) & rram_load_run  & (!cmd_user_write_dis) ? 3 : ... & rram_write_run & (!cmd_user_write_dis) ? 4 :
```

**Per-slot policy source (the ACRAM):** `acram2kx64`, `rrc.sv:424-432`, loaded at boot from ReRAM `brfsm==4` (`rrc.sv:143,360-361`), and rewritable at runtime by writing the 0x603D_C000 CFG region (`rrc.sv:358 rramcfg_vld`, `:361`). Decode `rrc.sv:691-705`:
```
691-697: core_rd_dis_k=keycfg[0]; core_wr_dis_k=keycfg[1]; sce_rd_dis_k=keycfg[2]; sce_wr_dis_k=keycfg[3];
         keytype_k=keycfg[15:8]; userid_k=keycfg[23:16]; akeyid=keycfg[31:24];
699-705: same layout for data slots, plus wrmode_d = datacfg[24];
```
Bypass conditions built into the checks: `& (userid_k[7:4] != 4'h0)` (line 717) and `& (userid_d[7:4] != 4'h0)` (line 726) — **a slot with owner nibble 0 has NO access control at all** (documented as "NO_OWNER … allow", `rrc.sv:627,631`). And `!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0)` (717) — `truststate[255]` is hardwired 1 (`rtl/modules/crypto_top/rtl/sce_sec.sv:121-123`), so `akeyid == 255` always passes the trustkey gate.

Address regions decoded by the RRC:
```
355:    localparam PM_KEY_REGION  = 16'h603F;      -> 0x603F_0000..0x603F_FFFF  key slots
356:    localparam PM_DATA_REGION = 16'h603E;      -> 0x603E_0000..0x603E_FFFF  data slots
644:    localparam PM_CODE_REGION_BORDER = 20'h603D_A;
686:    assign codesel = ( haddr_reg[31:12] < PM_CODE_REGION_BORDER );   // no lower bound
806-807: PM_CFGD_REGION = PM_CFGK_REGION = {16'h603D,2'b11}; -> 0x603D_C000..0x603D_FFFF (both aliases identical)
497:    one-way counters: haddr[23:16]==8'h3D & haddr[15:13]==3'b101 -> 0x603D_A000 / 0x603D_B000
870:    assign axi_info = suicide_reg ? suicide_info : haddr_reg[22];   // INFO/IFR block at 0x6040_0000
```

#### (B) SCE — `rtl/modules/crypto_top/rtl/sce_sec.sv`

```
61:    `theregrn( {coreuserselreg, coreuserreg} ) <=   ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) ? { 1'b0, coreuser_cm7 } :
62:                                                    ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_VEXD ) ? { 1'b1, coreuser_vex } : {coreuserselreg, coreuserreg};
64:    `theregrn( {sceusersel, sceuser} ) <= sceuserlock ? {coreuserselreg, coreuserreg} : {sceusersel, sceuser};
58:    assign sceuserlock = ( scemodereg == 0 ) && ~( scemode == scemodereg ) ;
70:    assign ahbscpvld = ahbs.hsel & ahbs.htrans[1] & ahbs.hreadym & ahbs.hready ;
72:    assign ahben =  mode_non ? 1'b1 :
73:                            ((sceusersel == 0 ) ? ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) : ( ahbs.hauser == daric_cfg::AMBAID4_VEXD )) &
74:                            ((sceusersel == 0 ) ? ( coreuser_cm7 == sceuser ) : ( coreuser_vex == sceuser ));
76:    ahb_gate #(.AW(32),.DW(32)) ahbsgate(.ahben,.ahbslave(ahbs),.ahbmaster(ahbm));
77:    assign ahbs_lock = devmode[0] ? 1'b0 : ~ahben;
81:    assign modequit = devmode[1] ? '0 : ~( scemodereg == 0 ) && ~( scemode == scemodereg ) ;
83:	assign sceresetnin = ~( modequit | ar_reset );
```
> **Integration mismatch:** lines 62/73/74 test for `AMBAID4_VEXD == 4'h4`, but the Vex's *peripheral/AHB* port — the only Vex port that reaches the SCE's AHB slave — drives `0xD` (`AMBAID4_VEXP`, `vexsys.sv:166`). The Vex path is therefore never recognised.

> `ahben == 1` unconditionally while `scemode == 0` (line 72, `mode_non`) — the reset state. In that state **any** master reaching 0x4002_0000 (CM7-P, MDMA, BDMA-AHB, SCE loopback) has unrestricted access to the SCE key RAM window.

Trust-state, the other SCE-side authority (feeds `trustkey[]` in the RRC): `sce_sec.sv:113-123`
```
117:    `theregrn( tsreg[i] ) <= ((hmac_kid==i)&mode_sec & hmac_pass) ? 'b1 : ((hmac_kid==i)&mode_sec & hmac_fail) ? 'b0 : tsreg[i];
123:    assign ts = { 1'b1, tsreg };
```
`sce_ts` is instantiated with `.resetn(resetn)` (`rtl/modules/crypto_top/rtl/sce.sv:298`) — the **external** `sysresetn`, *not* `sceresetn`. Everything else in the SCE uses `sceresetn` (`sce.sv:275`). So the trust bits **survive an SCE `ar_reset` and a `modequit` reset**.

#### (C) Places where privilege is NOT checked

* **No APB or AHB slave in this repo consumes `pprot` or `hprot`.** Verified by grep; only consumer of `hprot` is a passthrough in `rtl/modules/common/rtl/axisramc.sv:159`. `apb_mux` forwards `pprot` (`amba_components.sv:311`) to slaves that ignore it.
* The AHB demux has **no default slave**: unmapped addresses assert no `hsel`, `ahbslave.hready` is forced 1 and `hresp` 0 (`ahb_demux.sv:119,122`) → writes silently dropped, reads return 0, no fault.

---

## 2. BUS MASTERS — REACH AND WHAT STANDS IN THE WAY

### 2.1 Global address map (assembled from `daric_cfg_pkg.sv`, `bmxcore.sv`, `soc_coresub.sv`, `soc_ifsub.sv`)

| Range | Contents | Decoder |
|---|---|---|
| `0x0000_0000–0x1FFF_FFFF` | CM7 ITCM | `daric_cfg_pkg.sv:66` |
| `0x2000_0000–0x3FFF_FFFF` | CM7 DTCM | `daric_cfg_pkg.sv:65` |
| `0x4000_0000–0x4000_FFFF` | **RRC control SFRs** (`rrccr`, suicide AR) | `daric_cfg_pkg.sv:55` → `soc_coresub.sv:823-824` |
| `0x4001_0000–0x4001_FFFF` | coresub APB: `[0]`QFC@`0x4001_0000`, `[1]`MDMA-chnl@`..1000`, `[2]`MDMA-cfg@`..2000`, `[3]`**mailbox**@`..3000`, `[4]`sramtrm@`..4000` | `daric_cfg_pkg.sv:54`; `soc_coresub.sv:643,649-654`; stride 4 KB (`apb_mux` DECAW=4, `amba_components.sv:301`) |
| `0x4002_0000–0x4002_27FF` | **SCE unified crypto RAM (LKEY/KEY/SKEY/SCRT/MSG/HOUT/SOB/PKB/PIB/POB/PSOB/AKEY/AIB/AOB/RNGA/RNGB)** | `daric_cfg_pkg.sv:53` → `sce.sv:60-64` idx1 |
| `0x4002_4000–0x4002_5FFF` | SCE PKE RAM | `sce.sv:61` idx2 |
| `0x4002_8000–0x4002_FFFF` | SCE control APB (glbsfr@+0, scedma@+0x1000, hash@+0x3000, …) | `sce.sv:63,179-182` |
| `0x4003_0000–0x4003_FFFF` | (MDMA slot) — **tied off**: `ahbs_null coreahbmux3_null` `soc_coresub.sv:640` |
| `0x4004_0000–0x4004_FFFF` | apb1-system: `[0]`**sysctrl**, `[1]`WDT, `[2]`duart, `[3]`timer, `[4]`EVC, `[5]`**rbist trim** | `daric_cfg_pkg.sv:51`; `soc_top.sv:362,514,522,530,492,968` |
| `0x4005_0000–0x4005_FFFF` | apb2-security (**secsub**): `[2]`mesh@`0x4005_2000`, `[3]`sensorc@`..3000`, `[4]`gluechain@`..4000` | `daric_cfg_pkg.sv:50`; `soc_top.sv:714`; `secsub.sv:46,58,75,95` |
| `0x4006_0000–0x4006_FFFF` | apb3-always-on (**AO/PMU sysctrl**, over an async AHB bridge) | `daric_cfg_pkg.sv:49`; `soc_top.sv:830-838` |
| `0x5010_0000–0x5011_FFFF` | uDMA | `soc_ifsub.sv:132` |
| `0x5012_0000–0x5012_FFFF` | ifsub APB peripherals; `[2]`UDP, `[4]`**BIO/BDMA config**@`0x5012_4000`, `[5:8]`**BIO imem**, `[9:12]` BIO FIFO alias | `soc_ifsub.sv:131,349-372` |
| `0x5014_0000` | SDDC (instance commented out) | `soc_ifsub.sv:129,328` |
| `0x5020_0000–0x5020_FFFF` | USB device controller | `soc_ifsub.sv:130` |
| `0x5030_0000–0x5030_1FFF` | **AO SRAM (8 KB)** | `soc_ifsub.sv:128`; `soc_top.sv:841-849` |
| `0x6000_0000–0x603F_FFFF` | **ReRAM** (4 MB) incl. code, one-way counters @`0x603D_A000/B000`, ACRAM cfg @`0x603D_C000`, data slots @`0x603E_xxxx`, **key slots @`0x603F_xxxx`** | `daric_cfg_pkg.sv:64`; `rrc.sv:355,356,644,497` |
| `0x6040_0000` | ReRAM INFO/IFR block (`axi_info = haddr[22]`) | `rrc.sv:870` |
| `0x6100_0000–0x611F_FFFF` | Core SRAM banks 0/1 | `daric_cfg_pkg.sv:63` |
| `0x8000_0000–0x9FFF_FFFF` | QFC / XIP external flash | `bmxcore.sv:108,164` + `nic400_1` m3 |

### 2.2 Per-master reach

| # | Master | Interface | Routed by | Reachable ranges | Access control in the way |
|---|---|---|---|---|---|
| 1 | **CM7 AXI** `hauser=0x2` | `cm7_axim` → `nic1.s0` | `bmxcore.sv:291` | `0x6000_0000–0x9FFF_FFFF`: ReRAM (m0), SRAM0/1 (m1/m2), QFC (m3) | RRC coreuser+ACRAM checks (§1.6A). None for SRAM/QFC. CM7 MPU (config `daric_cfg_pkg.sv:117-127` **commented out**; `MPU` param comes from `daric_cfg::CM7CFG` which is also commented out). |
| 2 | **CM7 AHB-P** `hauser=0x8` | `cm7_ahbp` → `bmx33s[2]` | `bmxcore.sv:270` | `cm7_ahbs`, `core_ahb32` (all of `0x4000_0000–0x4006_FFFF`), `bmxif_ahb32` (all of `0x50xx_xxxx`) | `sce_sec.ahben` for `0x4002_xxxx` only. **Nothing** for sysctrl, secsub, AO/PMU, rbist, QFC, mailbox, BIO, uDMA, IFRAM, AO SRAM. |
| 3 | **Vex I-AXI** `0x3` / **D-AXI** `0x4` | `nic1.s3/.s4` | `bmxcore.sv:293-294` | ReRAM, SRAM0/1, QFC | RRC checks; `vex_mm_reg` used as the "privileged" bit. |
| 4 | **Vex AHB-P** `0xD` | `vex_ahbp` → `core_ahbp3[1]` → `ahb_mux3` → `cm7_ahbp` port of bmxcore | `soc_coresub.sv:613,616-624,598` | identical to #2 | Same as #2 — and its `0xD` tag matches **no** check in `sce_sec.sv` (§1.6B). |
| 5 | **SCE general DMA** `axim[0]`, `aruser=0x5` | `sce_axi32[0]` → `sce_axi_demux` | `bmxcore.sv:112-129` | `0x0000_0000–0x5FFF_FFFF` via AHB matrix (idx0) **and** `0x6000_0000–0x9FFF_FFFF` via nic400 (idx1) — i.e. **everything, including ReRAM key slots, ITCM/DTCM, all peripherals** | Address is entirely software-programmed: `scedma_amba.sv:384,400 axim.araddr = cr_axaddrstart + aximprt*4`. AxPROT is software-chosen in secure mode: `scedma_amba.sv:305 cr_axprot = mode_sec ? cr_opt[9:8]|3'h0 : ...`. AXI ID = `cr_segid` (`:385,401`), which becomes `keytype_in` in the RRC (`rrc.sv:674`). **No address whitelist.** |
| 6 | **SCE secure DMA** `axim[1]`, `aruser=0x6` | same | same | same | same |
| 7 | **MDMA** `hauser=0x7` | `mdma_ahb32` → `mdma_ahb_demux` | `bmxcore.sv:162-178` | `0x0000_0000–0x5FFF_FFFF` (idx1) and `0x6100_0000–0x9FFF_FFFF` (idx0). Comment: `// to nic_1, but no ReRAM` — **ReRAM `0x6000_0000–0x60FF_FFFF` is deliberately excluded** | Address-map exclusion only. Programmed from `0x4001_1000/2000` with `sfrlock` = 0. |
| 8 | **BDMA (BIO) memory AXI** `aruser=0x7` | `bdma_axi32` → `aximux_dma_pulp[1]` → `axi_mux_dma` → `axi_mux` → `nic_s2` → nic400 | `bmxcore.sv:199,215-221,254-260,292` | **ReRAM (m0), SRAM0/1, QFC** — the ReRAM exclusion applied to the MDMA is **not** applied here | `axil_filter` (see below) + RRC checks with `coreuser_in` falling through to `coreuser_cm7` (`rrc.sv:670-671`) |
| 9 | **BDMA (BIO) peripheral AHB** `hauser=0x0` | `bdma_ahb32` → `ahb_mux_slave[0]` → `bmx33s[1]` | `bmxcore.sv:225,229-233` | `cm7_ahbs`, `core_ahb32` (**all of `0x4000_0000–0x4006_FFFF`: SCE, sysctrl, secsub/tamper, AO/PMU, rbist**), `bmxif_ahb32` | `axil_filter` + `sce_sec.ahben`. `hauser=0` matches nothing. |
| 10 | **uDMA** `aruser=0xA` | `axiudma` → `axi_ahb_bdg` → `bmxifs[1]` → `ahb_bmxif` | `soc_ifsub.sv:99-116` | Confined to `bmxifm[0..2]` = IFRAM0, IFRAM1, and `bmxifm_map` (`soc_ifsub.sv:127-133`): uDMA regs, ifsub APB, USB, SDDC, AO SRAM. **Cannot reach the core bus.** | Address-map confinement only |
| 11 | **USB device (udc)** `aruser=0xB` | `sdahbm[0]` → `ahb_mux3` → `bmxifs[2]` | `soc_ifsub.sv:290-303` | Same confinement as #10 | Same |
| 12 | **SDDC** `hauser=0x0` | `sdahbm[1]` | `soc_ifsub.sv:307-327` | **Instance is commented out**, replaced by `ahbm_null sdahbm1` (`:328`) | n/a |
| 13 | **JTAG — IPT TAP** | `jtagipt` → `jtagtap` 5×64-bit registers | `soc_top.sv:909-921` | Not a bus master; drives `ipt_socreg`(RNG cfg, iptposel), `ipt_aoreg` (**PMU trim/config in the AO domain**), `ipt_padpo/padoe` (**direct pad drive, 64 bits**), `iptregout[4]` (ATPG mode bits), `iptregout[2]` (all SRAM trims) | Enabled only by `iptap_en = cmstest \| cmsbist \| cmsatpg` (`soc_top.sv:907`) and `jtags_resetn = enable & resetn & jtags.trst` (`jtagtap.sv:33`) |
| 14 | **JTAG — RRAM TAPs** `jtagrrc[0:1]` | direct into `trbcx1r32_daric_wrapper` `tck/tms/tdi/tdo` | `rrc.sv:968-1048, 1054-1135` | Raw ReRAM macro access, bypassing **all** of §1.6A | Gated by `bist_enable = ((cmscode == CMS_VRGN) \| (cmscode == CMS_TEST)) & (brfsm == 3'h5)` (`rrc.sv:884`) and, in the pad frame, by `cmstest` (`pad_frame_arm.sv:233-241`) |
| 15 | **JTAG — rbist TAP** `jtagrb` | `rbist_wrp` | `soc_top.sv:961-1009` | RAM trim registers + (post-insertion) MBIST engine ports into **all 28 RAM groups incl. SCE sceram/hashram/aesram/pkeram/aluram and the RRC ACRAM** | The `rbs.*` port is selected by `cmsbist` (`rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:127-131`); `cmsbist = cmstest` (`soc_top.sv:397`) |
| 16 | **SWD / CM7 DAP** | `swdio`, `clkswd` | `cm7sys.sv:380-381`; pad `pad_frame_arm.sv:219-220` | Full CM7 debug (halt, memory access via AHB-AP) | `clkswd_cm7` is ICG-gated by `cm7cfg_en` (`soc_coresub.sv:306`) — **no lifecycle gate found in this repo** |
| 17 | **Vex JTAG** | `jtagvex` (pins PAD_JTCK/TMS/TDI/TDO/TRST) | `vexsys.sv:347-352` | Full Vex debug | `assign .jtag_tdi(jtags.tdi & vexcfg_dev)`, `.jtag_tms(jtags.tms & vexcfg_dev)` — gated by **`vexcfg_dev = corecfg_devreg & vexcfg_en`** (`soc_coresub.sv:269`) |

### 2.3 The BDMA "whitelist" — documented guarantee vs. RTL

`docs/src/ch02-00-bio-overview.md:70`:
> "access to main memory is blocked by a whitelist, which by default is empty. So, before attempting to use the BDMA feature, one must first declare which regions of memory the BIO is allowed to access. This also helps prevent abuse of the BDMA as a method for bypassing host CPU security features."

Implementation, `rtl/modules/bio_bdma/rtl/bio_bdma.sv:2540-2577`:
```
2549:                match_write[k] = (s_axi_awaddr[31:12] >= base[k]) && (s_axi_awaddr[31:12] < bounds[k]);
2550:                match_read[k]  = (s_axi_araddr[31:12] >= base[k]) && (s_axi_araddr[31:12] < bounds[k]);
2556:        allow_write = |match_write | disable_filter;
2557:        allow_read  = |match_read  | disable_filter;
2562:    assign m_axi_awaddr = allow_write ? s_axi_awaddr : gutter;
2576:    assign m_axi_araddr = allow_read  ? s_axi_araddr : gutter;
```
Delta vs. the documented guarantee:
1. Out-of-range transfers are **not blocked** — they are **re-addressed to `gutter`**, which is a plain 32-bit software CR (`bio_bdma.sv:562-563` `sfr_mem_gutter @0xA0`, `sfr_peri_gutter @0xA4`), with **no range check on the gutter itself**. Pointing `mem_gutter` at any address makes the "filter" a no-op.
2. `disable_filter_mem` / `disable_filter_peri` are plain CR bits in `sfr_config @0x08` (`bio_bdma.sv:504-508`) with no lock.
3. `bio_bdma.sv:1478` — the **peripheral** filter is wired to `.disable_filter (disable_filter_mem)`. `disable_filter_peri` (declared `:325`, driven `:506`) is **never consumed**: dead signal, and one bit disables both filters.
4. Both filters share the *same* `filter_base[]`/`filter_bounds[]` arrays (`:1339-1340` and `:1476-1477`) — there is no separate memory vs. peripheral whitelist.
5. The whitelist registers live at `0x5012_40E0–0x5012_40FC` on the same APB used to program the BIO itself, with `sfrlock` = 0 — so any master that can drive the BIO can also rewrite its whitelist.
6. `bio_bdma.sv:1360,1373` gives the BDMA `AMBAID4_MDMA` (`0x7`), colliding with the MDMA and matching no branch in `rrc.sv:666-668`.

---

## 3. `devmode` / LIFECYCLE / DEBUG-MODE SIGNALS

### 3.1 `devmode` — sourced from **ReRAM**, not a fuse or a pad

```
rtl/modules/sysctrl/rtl/nvrcfgs.sv:82   localparam bit [31:0] cpudevmode = 32'h298ca435;
rtl/modules/soc_coresub/rtl/soc_coresub.sv:271
    `theregfull( hclk, resetn, corecfg_devreg , '0 ) <= ( nvrcfgdata.cfgcore.devena     == nvrcfg_pkg::cpudevmode );
soc_coresub.sv:268-269
    assign cm7cfg_dev   = corecfg_devreg & cm7cfg_en;
    assign vexcfg_dev   = corecfg_devreg & vexcfg_en;
soc_coresub.sv:509
    assign scedevmode = cm7cfg_dev|vexcfg_dev;
```
`nvrcfgdata` is the boot-read image of ReRAM word 12 (`nvrcfgs.sv:127`), captured by `brc` into flops that **reset to `'0`** (`rtl/modules/sysctrl/rtl/brc.sv:84-89` `theregrn` → IV `'0`, macro at `rtl/modules/common/rtl/template.sv`). So in the ASIC build `devmode = 0` until the boot read completes, then follows the ReRAM word.

> **FPGA build differs and is dev-mode-ON:** `brc.sv:120 assign nvrcfgdata = nvrcfg_pkg::defnvrcfg;` with `nvrcfgs.sv:87 devena : cpudevmode` — i.e. the FPGA/simulation default image has dev mode **enabled**. (`ifdef FPGA` only, `brc.sv:115-123`.)

What `devmode` gates:

| Consumer | Site | Effect when set |
|---|---|---|
| Vex JTAG | `vexsys.sv:347,349` `.jtag_tdi(jtags.tdi & vexcfg_dev)`, `.jtag_tms(jtags.tms & vexcfg_dev)` | Vex debug TAP is fed the real pins; otherwise held at 0 |
| Vex reset vector | `soc_coresub.sv:415-416` `.vexcfg_dev`, `.vexcfg_iv` | (see `vexsys`) |
| CM7 | `soc_coresub.sv:346` `.cm7cfg_dev(cm7cfg_dev)` | passed into `cm7sys` |
| **SCE — all five security interlocks** | `rtl/modules/crypto_top/rtl/sce.sv:131` `assign devmode_sce = devmode ? '1 : nvrcfg[28];` | with the comment block at `sce.sv:132-136`: `[0]` AHB-enable bypass, `[1]` mode-quit reset bypass, `[2]` scemode value-lock bypass, `[3]` PKE AHB-slave lock bypass, `[4]` ALU secure bypass. Consumed at `sce.sv:138-139`, `sce_glbsfra.sv:78`, `sce_sec.sv:77,81`. |

> Note `sce.sv:131`: even with `devmode == 0`, `devmode_sce` is taken **byte-wise from ReRAM `cfgsce[28]`** — a second, independent, ReRAM-controlled way to disable all five SCE interlocks. `nvrcfg` = `nvrcfgdata.cfgsce` (`soc_coresub.sv:545`).

**In the field vs. on the bench:** identical mechanism. There is no fuse, no pad, no one-way counter, and no anti-rollback on `devena`. `devena` lives in the ReRAM CFG block (`nvrcfgs.sv:75`, word 12), i.e. in the address range covered by §1.6A's `cfg_access_error` check (`0x603D_C000`) — the *only* protection on the dev-mode word is `cfg_rd_dis`/`cfg_wr_dis` bits in ACRAM plus `cfg_prev_dis` requiring `coreuser_in[5]|coreuser_in[4]` (boot0/boot1). It is *rewritable at runtime* by boot0/boot1-classified code.

### 3.2 Chip-Mode-Select (CMS) — the real lifecycle gate

Source: **3 external pads** `PAD_WMS0/1/2` (`rtl/asic_top/rtl/pad_frame_arm.sv:214-216`, `padcell_i #(.pu('0), .pd('1))` — pulled **down**) plus one 128-bit word read from ReRAM.

```
rtl/modules/sysctrl/rtl/cms.sv:23-30
  typedef enum logic [7:0] { CMS_NONE=8'h00, CMS_VRGN=8'h37, CMS_ATPG=8'h5B,
                             CMS_TEST=8'hA6, CMS_USER=8'hFB, CMS_SCDE=8'hFF } cmscode_e;
cms.sv:34-39
  typedef enum logic [CMSDW-1:0] {
    CMSDAT_VRGNMODE     = '0                                 ,
    CMSDAT_TESTMODE     = '0 ,
    CMSDAT_ATPGMODE     = '0 ,
    CMSDAT_USERMODE     = '0
  } cmsdata_e;
```
> **All four CMS "patterns" are `128'h0`.** Every `cmsdatareg == CMSDAT_*` comparison in `cms.sv:121-135` is the same test: "is the ReRAM CMS word zero?". The ReRAM default is also `CMSDAT_USERMODE` = 0 (`nvrcfgs.sv:102-105`). The mode therefore collapses to a function of two pads.

```
cms.sv:91-100
    `theregrn( cmspadregs[0] ) <= cmspad;
    `theregrn( cmspadregs[1] ) <= { cmspadregs[0][0:1], 1'b0 };      // bit[2] forced to 0
    `theregrn( cmspadlock ) <= ( cmspadcnt == CMSPADCYC );            // CMSPADCYC = 128
    `theregrn( cmspadout ) <= ~cmspadlock ? cmspadregs[1] : cmspadout;
cms.sv:119-137   (cmspadout = {WMS0, WMS1, 1'b0})
    3'bxx1: ...                                     // unreachable: LSB forced 0 at line 92
    3'b0x0: cmscodepre = CMS_USER;                  // WMS0 = 0  -> USER
    3'b100, 3'b110:
        cmscodepre = ( cmsdatareg == CMSDAT_VRGNMODE ) ? ( cmspadout[1] ? CMS_VRGN : CMS_ATPG ) :
                     ( cmsdatareg == CMSDAT_TESTMODE ) ? ( cmspadout[1] ? CMS_TEST : CMS_ATPG ) :
                     ( cmsdatareg == CMSDAT_USERMODE ) ? CMS_USER : CMS_SCDE;
cms.sv:152-158
    `theregfull(clk, cmsresetn, cmsatpg_reg, 1'b0) <= ( cmscodereg == CMS_ATPG ) | cmsatpg_reg;   // sticky
    `theregrn( cmstestreg ) <=   cmscodereg == CMS_TEST | cmscodereg == CMS_VRGN;
    `theregfull( clk, resetn, cmscodereg, CMS_NONE ) <= cmsdataregvld & cmspadlock ? ( aocmsuser ? CMS_USER : cmscodepre) : cmscode;
    `theregrn( cmsscdereg ) <= ( cmscodereg == CMS_SCDE ) | cmsscdereg;                            // sticky
cms.sv:196
    assign cmserror = cmsatpg? 1'b0 : cmspaderror;      // -> soc_top.sv:342 .socresetn(socresetn & ~cmserror)
```
Effective truth table with the ReRAM word at its default (0):
* `WMS0=0` → **CMS_USER**
* `WMS0=1, WMS1=1` → **CMS_VRGN** (⇒ `cmstest=1`, `cmsbist=1`)
* `WMS0=1, WMS1=0` → **CMS_ATPG** (⇒ full scan)
* ReRAM word **non-zero** and `WMS0=1` → **CMS_SCDE = suicide/mass-erase** (`rrc.sv:307`)

The one mitigation, a sticky AO-domain latch:
```
rtl/modules/ao/rtl/ao_top.sv:144
    `theregfull( clksysao_undft, porresetn_undft, aocmsuser, '0) <= aocmsuser | cmsuser;
```
`aocmsuser` forces `CMS_USER` on all subsequent mode evaluations (`cms.sv:155`). It clears only on `porresetn_undft`, which comes from
```
rtl/modules/ao/rtl/ao_sysctrl.sv:422   assign por = ~pmu_POR & padresetn ;
ao_sysctrl.sv:424-431 aoresetgen genporreset(... .resetn(por), .resetnin(por), .resetnout(porresetn_undft));
```
i.e. **`padresetn` = the external `PAD_XRSTn` pad** (`pad_frame_arm.sv:218`). Pulling XRSTn low clears the sticky USER latch without a power cycle; SRAM/TCM/IFRAM/AO-SRAM/BIO-RAM contents are not cleared by any reset.

### 3.3 What `cmstest` / `cmsbist` / `cmsatpg` unlock

```
soc_top.sv:397  assign cmsbist = cmstest;
soc_top.sv:907  assign iptap_en = cmstest | cmsbist | cmsatpg;                   // IPT JTAG TAP live
soc_top.sv:928  assign ipt_aoreg  = cmsuser ? aopmutrmdata : iptregout[1];       // JTAG owns PMU trims when NOT in user mode
pad_frame_arm.sv:232-250  jtagrrc[0/1].tms/tdi/trst and jtagrb.tms/tdi/trst = cmstest & <pin>;  jtagipt = (cmstest|cmsatpg) & <pin>
pad_frame_arm.sv:262-269  pbtestpo[1,3,5..15] = cmstest ? {jtagrrc[1].tdo, jtagrb.tdo, iptpo[0..5]} : scanout[..]
rrc.sv:884  assign bist_enable = ((cmscode == CMS_VRGN) | (cmscode == CMS_TEST)) & (brfsm == 3'h5);
rrc.sv:898-899  ICG rramicg_tck0/1 ( .CK(jtag[0/1].tck), .EN(bist_enable), .SE('0), .CKG(rramclk_tck0/1) );
ram_1rw_s.sv:124-131  rbspmux: cmsbist selects rbs.ram{clk,cen,gwen,wen,addr,wdata} into every RAM macro, and
                       `assign rbs.ramrdata = cmsatpg ? undft_q : rb_q;`   -> full read-back
ao_sysctrl.sv:285-286  assign jtagit_set0 = soctrmvld & jtagit_setreg0 & ( cmsatpg | cmstest );
                       assign jtagit_set  = soctrmvld & jtagit_setreg  &   cmstest;   // JTAG writes PMU/OSC trims
trng.sv:188-191  t_rnglf_sel/en, t_rnghf_en forced to '1 and t_rnghf_cfg <= ipt_rngcfg when cmstest
soc_top.sv:944  iptposel == 3 ? { iptorndlf, iptorndhf, iptpopll, iptporng, iptpoosc }   // raw RNG oscillator out to pads
soc_coresub.sv:307-311  sysresetn_cm7 / coreresetn_cm7 / resetn_vex = cmsatpg ? 1'b1 : ...   // resets defeated in ATPG
```
Also `cmsatpg` forces `sysresetn = coreresetn = atpgrst` (`sysctrl.sv:810-811`), `porresetn = atpgrst` (`ao_sysctrl.sv:431`), and `resetgen.resetnout = cmsatpg | resetext` (`sysctrl.sv:918`).

### 3.4 Core-select lifecycle (`coreselcm7` / `coreselvex`)

```
nvrcfgs.sv:83-84   coreselcm7_code = 32'h7e20a453;  coreselvex_code = 32'h6a428c82;
soc_coresub.sv:272-273
    `theregfull( hclk, resetn, cm7cfg_enreg   , '0 ) <= ( nvrcfgdata.cfgcore.coreselcm7 == nvrcfg_pkg::coreselcm7_code );
    `theregfull( hclk, resetn, vexcfg_enreg   , '0 ) <= ( nvrcfgdata.cfgcore.coreselvex == nvrcfg_pkg::coreselvex_code );
soc_coresub.sv:283-284
    assign cm7cfg_en = ~vexcfg_enreg | cm7cfg_enreg;
    assign vexcfg_en =  vexcfg_enreg;
```
Both can be enabled simultaneously (both magic words present). Before the ReRAM boot read finishes, `vexcfg_enreg = 0` ⇒ **`cm7cfg_en = 1`, `vexcfg_en = 0`** — the CM7 is the default core out of reset.

Reset vector: `soc_coresub.sv:263-266`, `cm7cfg_iv = `ambarrb(m7_init)` — an 8-bit ReRAM field × 16 KB into `0x6000_0000`.

---

## 4. SECURITY LOCK / WRITE-PROTECT BITS — COMPLETE INVENTORY

`sfrlock` semantics: `rtl/modules/amba/rtl/apb_sfr.sv:333` `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` (and `:378` for the per-SFR variant; AHB equivalent `rrc.sv:1252`).

| # | Lock | File:line | Reset value | What clears / changes it | Notes |
|---|---|---|---|---|---|
| L1 | `soc_top.sfrlock` → `sysctrl.sfrlock` | declared `rtl/asic_top/rtl/soc_top.sv:217`, used `:361` `.sfrlock (sfrlock\|'0)` | **undriven net** | n/a | `logic sfrlock;` has **no assignment anywhere in `soc_top.sv`** (only 2 occurrences in the file). The entire sysctrl SFR write-protect is dead. |
| L2 | `sce_glbsfr.sfr_scemode` lock | `rtl/modules/crypto_top/rtl/sce_glbsfra.sv:78` `.sfrlock(~devmode & (\|cr_scemode))` | `cr_scemode = 2'b00` (unlocked) | any SCE reset (`sceresetn`, `sce.sv:224`) | Write-once out of 0; `devmode` (`devmode_sce[2]`, `sce.sv:229`) fully bypasses it |
| L3 | `sce_sec.ahbs_lock` / `ahben` | `rtl/modules/crypto_top/rtl/sce_sec.sv:72-77` | `ahben = 1` while `scemode == 0` | leaving `mode_non`; `devmode[0]` forces `ahbs_lock = 0` | The SCE crypto-RAM window `0x4002_0000` is **wide open in the reset state** |
| L4 | `sce_sec.modequit` → SCE reset | `sce_sec.sv:81-83` | `scemodereg = 0` | `devmode[1]` disables it entirely | Forces SCE reset + RAM clear on mode downgrade |
| L5 | `rrccr[12]` — code-region access-check enable | `rtl/modules/rrc/rtl/rrc.sv:778` `assign code_access_error = code_access_error_pre & rrccr[12];` | **`0`** — `ahb_cr_ECO #(.A('h00), .DW(32))` with default `IV = 32'h0` (`rrc.sv:274`, `:1144`) | `coreresetn` | **Every `rrccr` write force-sets bit 12**: `rrc.sv:1258` `sfrdatarr[i] <= ( sfrsel[i] & reg_write_en ) ? reg_wdata\|32'h0000_1000 : sfrdatarr[i];` — but until the first write, ReRAM **code**-region access control is disabled |
| L6 | `rrccr[10]`, `[11]`, `[13]`, `[14]` — key/data/cfg/info check enables | `rrc.sv:718-720, 727-729, 783-785, 823-825` | n/a | n/a | **All four were removed by ECO** (`//#eco16`, e.g. `//    assign key_access_error = key_access_error_pre & rrccr[10];` then `assign key_access_error = key_access_error_pre;`) — those four checks are now always on |
| L7 | `rrccr[15]` — RRC access-error → NMI | `rrc.sv:292` `assign rrcnmi = rrcint & rrccr[15];` | `0` | `coreresetn` | Access-control violations raise **no NMI** by default |
| L8 | `rrccr[31:16]` — one-way-counter event enables | `rrc.sv:513` | `0` | `coreresetn` | — |
| L9 | `coreuser_protect` (Vex) | `rtl/modules/vexriscv/rtl/cram_axi.sv:22889-22895`, used `:20878` | `0` | **`sys_rst`** = `~(coreresetn & vexcfg_en)` | Set-only-to-1 flop; a warm `coreresetn` (incl. the software reset L10) re-opens the Vex coreuser LUT, map, uservalue and enable |
| L10 | `sysctrl sfr_rcurst0/1` — software resets | `rtl/modules/sysctrl/rtl/sysctrl.sv:871-872` `apb_ar #(.A('h80), .AR('h55aa)) sfr_rcurst0 (.ar(sysreset_sw)); apb_ar #(.A('h84), .AR('h55aa)) sfr_rcurst1 (.ar(corereset_sw));` | n/a | n/a | Reachable by **any** master at `0x4004_0080/84`; `sfrlock` = L1 (dead). Feeds `sysresetgen`/`coreresetgen` (`sysctrl.sv:794,803`) |
| L11 | `rrc sfr_rrcar` — **ReRAM suicide** | `rtl/modules/rrc/rtl/rrc.sv:286` `ahb_ar #(.A('hF0), .AR(PM_RRAM_SUICIDE)) sfr_rrcar (.ar(rrcar_suicide), .sfrlock(1'b0), .*);` with `:256 PM_RRAM_SUICIDE = 16'h2468` | n/a | n/a | Write `0x2468` to **`0x4000_00F0`** → mass erase (`rrc.sv:307`). `sfrlock` hardwired 0, no coreuser check on the RRC SFR path (§1.6 checks are on the AXI array path only) |
| L12 | `sce_glbsfr sfr_arrst / sfr_arclr` | `sce_glbsfra.sv:86-87` `apb_ar #(.A('h1c), .AR(32'h5a)) sfr_arrst (.ar(ar_reset)); apb_ar #(.A('h1c), .AR(32'ha5)) sfr_arclr (.ar(ar_clrram));` | n/a | n/a | Software SCE reset / crypto-RAM wipe; no lock |
| L13 | `mesh.sfrlock` | `rtl/modules/sec/rtl/mesh.sv:46` `` `theregrn( sfrlock ) <= '0; `` | hardwired 0 | — | `cr_mldrv` (`:53`) / `cr_mlie` (`:54`) reset to `'0` ⇒ **mesh drive and interrupt-enable are OFF at reset** |
| L14 | `sensorc.sfrlock` | `rtl/modules/sec/rtl/sensorc.sv:57` `` `theregrn( sfrlock ) <= '0; `` | hardwired 0 | — | see L15/L16 |
| L15 | `sensorc.cr_vdmask0` (IRQ mask) | `sensorc.sv:67` `.IV({VDC{1'b1}})` | **all-ones = all voltage-tamper IRQs masked** | any write | `sr_vdsr = vdflag & ~cr_vdmask0` (`:91`) |
| L16 | `sensorc.cr_vdmask1` (reset mask) | `sensorc.sv:68` `.IV({VDC{1'b1}})`; used `:93` `` `theregfull(clksys, resetn, vdresetnreg, '1 ) <= & ( cr_vdmask1 ? '1 : ~vdflag ); `` | **all-ones = voltage-tamper reset disabled** | any write | The 6-bit `cr_vdmask1` is used as a **scalar** ternary condition, not bitwise — *any* set bit disables the tamper reset for *all* detectors. This is the only path to `secresetn` (`soc_top.sv:712` `.vdresetn(secresetn)`) → `sysresetgen` (`sysctrl.sv:794`). |
| L17 | `sensorc.sfr_vdip_test` / `sfr_ldip_test` | `sensorc.sv:79,81` | `0` | any write | Software can drive the sensor self-test inputs directly |
| L18 | `gluechain.sfrlock` + `sfr_gcrst` + `sfr_gctest` | `rtl/modules/sec/rtl/gluechain.sv:42,50,51`; used `:55,58` `assign gluenet[i][0] = cmsatpg ? '0 : gluetest[i]; assign glueresetn[i] = cmsatpg ? '0 : gluerst[i] & resetn;` | `gluerst = 0` ⇒ **glue chain held in reset** | any write | Anti-tamper glue chain is disabled until software enables it; software also drives its stimulus |
| L19 | `trng.sfrlock` | `rtl/modules/crypto_top/rtl/trng.sv:52` `` `theregrn( sfrlock ) <= '0; `` | hardwired 0 | — | see §6 |
| L20 | `rbist_wrp.sfrlock` (RAM trim CRs) | `rtl/modules/rbist/rtl/rbist_wrp.sv:161` `assign sfrlock = '0;` | hardwired 0 | — | Any master at `0x4004_5000` can rewrite the timing trim of **all 28 RAM groups** incl. SCE/ReRAM ACRAM |
| L21 | `ao_sysctrl.sfrlock` (PMU/OSC trim, wakeup, pad-pull) | `rtl/modules/ao/rtl/ao_sysctrl.sv:362` `assign sfrlock = '0;` | hardwired 0 | — | PMU voltage trims at `0x4006_0020/24/28/2c`, `sfr_pmupdar @0x44` |
| L22 | `mbox_apb.sfrlock` | `rtl/modules/mbox/rtl/mbox.sv:104` `assign sfrlock = '0;` | hardwired 0 | — | CM7↔Vex mailbox has no privilege check |
| L23 | `qfc.sfrlock` (incl. XIP AES key) | `rtl/modules/core/rtl/qfc.sv:176` `` `theregrn( sfrlock ) <= '0; `` ; key at `:202` `apb_cr #(.A('h40), .DW(32), .SFRCNT(4)) cr_aeskey` | hardwired 0 | — | Key is **write-only on read-back** (`cr_aeskey.prdata32` is *not* in the `apbx.prdata` OR-list, `qfc.sv:182-189`) but freely **writable** by anyone at `0x4001_0040..0x4001_004C`; enable at `0x4001_0050` |
| L24 | `bio_bdma` filter/gutter/config CRs | `bio_bdma.sv:504-508, 562-563, 620-627`; `sfrlock` comes from `` `apbs_common `` (`apb_sfr.sv:19-23`) which sets it to 0 | `filter_base/bounds = 0`, `gutter = 0`, `disable_filter_* = 0` | — | See §2.3 |
| L25 | `sce scedma_ac` rule source | `rtl/modules/crypto_top/rtl/scedma_ac.sv:40,66` `assign nvrrule_enable = (nvracrules[29] == 8'h5a); ... chnlacrules[j] = nvrrule_enable ? nvracrules[j] : ACRULEs[j].accessrule;` | ReRAM-controlled | ReRAM `cfgsce` | Whole SCE DMA channel/segment rule table is overridable from ReRAM |
| L26 | `sce acenable` | `rtl/modules/crypto_top/rtl/sce.sv:370` `assign acenable = mode_sec;` with `scedma_ac.sv:47` `assign chnlac[i] = acenable ? chnlacrule : '1;` | disabled (`scemode = 0`) | leaving `mode_non` | **All SCE internal segment access control is OFF unless `scemode[1] == 1`** |
| L27 | `nvrcfgdata.cfgrrsub.tkey_en[4:2]` — trustkey enforcement per region | `rrc.sv:607-609, 761-763` | ReRAM; default `tkey_en : '0` (`nvrcfgs.sv:68`) | ReRAM CFG write | Default = trustkey linkage disabled for boot1/fw0/fw1 |
| L28 | `nvrcfgdata.cfgcore.qfc_disable` | `soc_coresub.sv:287` `` `theregfull( pclk, resetn, qfc_en, '1 ) <= ( nvrcfgdata.cfgcore.qfc_disable == 'h0 ); `` | **`'1` = QFC enabled** at reset | ReRAM | Reset value is *permissive*; the disable only takes effect after boot read |
| L29 | `ip_user_cmd` / `bist_enable` interlock | `rrc.sv:884` | — | CMS mode | see §3.3 |

**Registers that look like locks but are not:** `soc_top.sv:772 .ioxlock('0)` (ifsub IOX lock tied off); `rrc.sv:274-286` — every RRC SFR is instantiated with `.sfrlock(1'b0)` literally.

---

## 5. RESET AND POWER-DOMAIN TOPOLOGY vs. SECURITY STATE

### 5.1 Reset tree

```
PAD_XRSTn ──padcell_i(pu=1)──► padresetn                      (pad_frame_arm.sv:218)
pmu_POR ────┐
            ├─► por = ~pmu_POR & padresetn                    (ao_sysctrl.sv:422)
            └─► aoresetgen(10 clk32k) ─► porresetn_undft      (ao_sysctrl.sv:424-430)
                porresetn = cmsatpg ? atpgrst : porresetn_undft (ao_sysctrl.sv:431)

socresetnin = cmsatpg ? 1 : ~aopdreg & (&rstsrc)              (ao_sysctrl.sv:442-443)
rstsrc      = {BGRDY,VR25RDY,VR85ARDY,VR85DRDY,~POR} | rstcrmask   (ao_sysctrl.sv:432)  ← rstcrmask is a CR, IV=5'h1f (ao_sysctrl.sv:382)
aoresetgen(312×32 kHz ≈ 10 ms), resetnin = padresetn & socresetnin
   ──► socresetn_undft ; socresetn = cmsatpg ? atpgrst : socresetn_undft  (ao_sysctrl.sv:444-451)

sysresetgen: resetnin = { socresetn, vdresetn(=1'b1, soc_top.sv:373), secresetn, ~sysreset_sw }
   ──► sysresetn_unbuf ; sysresetn = cmsatpg ? atpgrst : sysresetn_unbuf  (sysctrl.sv:790-796, 810)
   NOTE soc_top.sv:342 passes `.socresetn(socresetn & ~cmserror)` into sysctrl

coreresetgen: resetnin = { padresetn, sysresetn, cmsresetn, wdtresetn, ~corereset_sw }
   ──► coreresetn ; coreresetn = cmsatpg ? atpgrst : coreresetn_unbuf     (sysctrl.sv:799-805, 811)
   cmsresetn = ( cmscode == CMS_USER ) & brdone                            (sysctrl.sv:787)
   wdtresetn: `theregfull( pclk, sysresetn, wdtresetn, '1) <= ~wdtreset;   (soc_top.sv:519)

secresetn ◄── secsub.vdresetn ◄── sensorc.vdresetn                        (soc_top.sv:712; sensorc.sv:93-94)
sceresetn ◄── sceresetgen(resetn=resetn(=sysresetn), resetnin=~(modequit|ar_reset))  (sce.sv:310-318)
resetn_vex = cmsatpg ? 1 : coreresetn & vexcfg_en                          (soc_coresub.sv:311)
sysresetn_cm7 / coreresetn_cm7 = cmsatpg ? 1 : {sys,core}resetn & cm7cfg_en (soc_coresub.sv:307-308)
qfcresetn  = scresetgen(resetn, ~arreset)                                  (qfc.sv:225-232)
resetnbio  = cmsatpg ? 1 : resetn                                          (soc_ifsub.sv:337)
```

**Reset ordering / hierarchy (weakest → strongest):**
`corereset_sw` / `wdtreset` ⊂ `coreresetn` ⊂ `sysreset_sw` / tamper(`secresetn`) ⊂ `sysresetn` ⊂ `socresetn` (AO POR / brownout) ⊂ `padresetn` (`PAD_XRSTn`) ⊂ `pmu_POR` (`porresetn`).

### 5.2 What each reset preserves / destroys (security-relevant)

| State | Clock/reset domain | Survives `coreresetn`? | Survives `sysresetn`? | Survives `socresetn`? | Survives `padresetn`/POR? |
|---|---|---|---|---|---|
| `coreuser` (CM7) | `fclk_cm7` / `sysresetn_cm7` (`cm7sys.sv:776`) | yes | no (→`8'h00`) | no | no |
| Vex `coreuser_protect` lock | `sys_clk` / `sys_rst=~resetn_vex` (`cram_axi.sv:22892`) | **no** | no | no | no |
| Vex coreuser LUT/map/uservalue | same | **no** | no | no | no |
| `sceuser`, `scemode`, `scemodereg` | `clk` / `sceresetn` (`sce_sec.sv:59,64`) | yes (unless modequit) | no | no | no |
| **SCE `truststate` (`tsreg`)** | `clk` / **`resetn` = `sysresetn`** (`sce.sv:298`, `sce_sec.sv:117`) | **yes** | no | no | no |
| SCE crypto RAM contents | cleared by `sceramclr` = `(initregs==4'h7)\|ar_clrram` (`sce_sec.sv:85-87`), clear range `0 .. SEGADDR_RNGA-1` (`sce.sv:415`) | yes | **cleared** on `sceresetn` re-assert | cleared | cleared |
| **Core SRAM banks 0/1, ITCM, DTCM, caches, IFRAM0/1, AO SRAM, BIO RAM, UDC RAM, ACRAM** | SRAM macros | **yes** | **yes** | **yes** | **yes** — nothing zeroizes them |
| `hauser_reg`, `haddr_reg`, `ahb_*_flag`, `axprot_reg`, `vex_mm_reg` (RRC) | `clktop` / `coreresetn` (`rrc.sv:541-549, 660-664`) | no | no | no | no |
| `rrccr` (incl. L5 bit 12) | `hclk` / `coreresetn` (`rrc.sv:274`) | **no → back to `0`** | no | no | no |
| `brdatreg[31:0]` (ReRAM boot image: ACRAM seed, IFR read/write-disable bytes, `user_code_cfg_*`) | `clksys` / `sysresetn` (`rrc.sv:156`) | **yes** | no | no | no |
| `brfsm`, `brdone` | `clksys` / `sysresetn` (`rrc.sv:136,146`) | yes | no | no | no |
| `nvrcfgdata` (devena, coresel, coreuser_filtercyc, region map, tkey_en) | `clk`=`clksys` / `sysresetn` (`brc.sv:84-89`) | **yes** | no (→ all `'0`) | no | no |
| `corecfg_devreg`, `cm7cfg_enreg`, `vexcfg_enreg`, `coreuser_filtercyc` | `hclk` / `resetn`=`sysresetn` (`soc_coresub.sv:271-274`) | **yes** | no | no | no |
| `cmscodereg`, `cmsuserreg`, `cmstestreg` | `clksys_undft` / `sysresetn_undft` (`cms.sv:155-157`) | yes | **no — CMS is re-evaluated** | no | no |
| `cmsatpg_reg` (sticky ATPG) | `clksys_undft` / `cmsresetn = socresetn_undft & sysresetn_undft` (`cms.sv:75,152`) | yes | **no** | no | no |
| `cmsscdereg` (sticky suicide) | `clksys_undft` / `sysresetn_undft` (`cms.sv:158`) | yes | no | no | no |
| **`aocmsuser` (sticky USER-mode latch)** | `clksysao_undft` / **`porresetn_undft`** (`ao_top.sv:144`) | **yes** | **yes** | **yes** | **no — cleared by `PAD_XRSTn`** |
| `cmspaderror` | `clk` / `chipresetn`=`socresetn_undft` (`cms.sv:97`) | yes | yes | no | no |
| AO PMU trims / `pmucrreg` / `osccrreg` / `rstcrmask` / `wkupmask` | `clksysao` / `porresetn` (`ao_sysctrl.sv:246-272`) | yes | yes | yes | no |
| RAM trims (`rbist_wrp.trmdat`) | `clksys` / `sysresetn` (`rbist_wrp.sv:194`) | yes | no | no | no |
| sysctrl clock/PLL/gating CRs (`aclkgr..pclkgr` IV `'hff`, `cgusec`, `cgulp`, PLL M/N/F/Q) | `pclk` / `coreresetn` (via `` `apbs_common ``) | **no** | no | no | no |
| Tamper config: `cr_mldrv`, `cr_mlie` | `pclkmesh` / `resetn`=`coreresetn` (`soc_top.sv:704`; `mesh.sv:53-54`) | **no → OFF** | no | no | no |
| Tamper config: `cr_vdmask0/1`, `cr_vdcfg`, `vdena`, `vdtst` | `pclk` / **`porresetn`** (`soc_top.sv:703` `.porresetn(socresetn)`; `secsub.sv:73` `.resetn(porresetn)`) | **yes** | yes | **no → masks back to all-ones** | no |
| Gluechain `gluerst`, `cr_gcmask`, `gluetest` | `pclk` / `resetn`=`coreresetn` (`secsub.sv:93`) | **no → chain held in reset** | no | no | no |
| TRNG config (`cr_src` incl. `chaincut`, `cr_ana`, `cr_postproc` incl. `healthtest_en`/`drng_en`, `dr_psz_str`, `sfr_buf`) | `clk`=`clksub[4]`(SCE) / `sceresetn` (`sce.sv:224` chain) | yes | no | no | no |
| BIO filter/gutter/config | `pclkbio` / `resetnbio`=`resetn`=`coreresetn` (`soc_ifsub.sv:337,767`) | **no → base/bounds/gutter = 0** | no | no | no |
| QFC XIP AES key `cr_aeskey` | `pclkqfc` / `resetn` (`qfc.sv`, `` `apbs_common `` → `resetn` = coresub `resetn` = `sysresetn`) | **yes** | no | no | no |
| `wdtresetn` | `pclk` / `sysresetn`, IV `'1` (`soc_top.sv:519`) | yes | no | no | no |

### 5.3 Power domains

* **AO domain** (`clksysao`, `clkao`, `clk32k`): `ao_top` / `ao_sysctrl` / `aoram` / `dkpc` / PMU. Separate `porresetn` from `pmu_POR & padresetn`. Isolation cell control: `ao_iso_enable = cmsatpg ? 0 : pdisoreg` (`ao_sysctrl.sv:513-522`), `pdisoen` is a CR bit (`ao_sysctrl.sv:379`, IV `3'h6`). Bridged to the SoC bus at `0x4006_0000` through `ahbasync` + `apb_bdg` (`soc_top.sv:830-838`) — an **asynchronous CDC with no identity or privilege filter**.
* **SoC domain** (`clksys`/`clktop`/`fclk`/`aclk`/`hclk`/`iclk`/`pclk`): everything else. Deep-sleep/power-down handshake `pdresetn = cmsatpg ? atpgrst : coreresetn & ~wkupvld_async & coresleep` (`sysctrl.sv:772`) and `pad_reton`/`pad_retoff` (`soc_top.sv:356-357`).
* **RRAM sleep**: `ip_user_nap_i` / `ip_user_pd_i` gated by `rrccr[0]` and `rramsleep` (`rrc.sv:874-875`); `rramsleep = ipsleep[2]` (`soc_top.sv:607`).
* **CDC crossings carrying security state that are *not* synchronised:** `coreuser`/`coreuser_vex` from `fclk_cm7`/`aclk` into `clktop` (RRC `rrc.sv:670-671`) and into `clksce` (`sce_sec.sv:61`); `vex_mm` from `aclk` into `clktop` (`rrc.sv:664`); `sceuser` from `clksce` into `clktop` (`rrc.sv:670,837`); `truststate[255:0]` from `clk`(SCE) into `clktop` (`rrc.sv:717,761-763`, `soc_coresub.sv:836`). Only the *error* reports get `sync_pulse` (`rrc.sv:830-834`).

---

## APPENDIX — HIGH-CONFIDENCE LEADS FOR THE DOWNSTREAM FINDERS

Ranked, each anchored. Each still needs an independent finder to confirm exploitability end-to-end.

1. **`cms.sv:34-39` — all four CMS mode patterns are `128'h0`.** Lifecycle (USER vs. TEST/VRGN/ATPG/SCDE) reduces to two external pads `PAD_WMS0/1`, defeating the ReRAM-word half of the mode gate.
2. **`ao_top.sv:144` + `ao_sysctrl.sv:422` — the sticky USER latch is cleared by the external `PAD_XRSTn` pad.** Combined with (1): XRSTn pulse + WMS pads ⇒ re-enter TEST/VRGN with all SRAM (`core_srambank`, ITCM, DTCM, IFRAM, AO SRAM, BIO RAM, ACRAM) contents intact and JTAG/BIST read-back live (`ram_1rw_s.sv:127-131`, `rrc.sv:884,898-899`, `pad_frame_arm.sv:232-250`).
3. **`soc_top.sv:217/361` — `sfrlock` is an undriven net.** The sysctrl write-protect (clock/PLL config, software resets, IPC) is inert.
4. **`rrc.sv:670-671` — `coreuser_mux` has no default.** BDMA(`0x7`/`0x0`), MDMA(`0x7`), uDMA(`0xA`), udc(`0xB`) all silently inherit `coreuser_cm7`; and with `cm7sel=vexsel=scesel=0` the per-slot `core_rd_dis_k/core_wr_dis_k/core_rd_dis_d/core_wr_dis_d` terms and the `pri_op`/`vex_mm` privilege terms in `rrc.sv:712-726` all evaluate to 0.
5. **`bmxcore.sv:162-165` vs `:199` — the ReRAM exclusion applied to the MDMA is not applied to the BDMA's AXI master.** `bdma_axi32` reaches `nic1.m0` (ReRAM) directly.
6. **`bio_bdma.sv:2562,2576` + `:562-563` — "whitelist" redirects to a software-programmable `gutter` instead of blocking.** Contradicts `docs/src/ch02-00-bio-overview.md:70`.
7. **`bio_bdma.sv:1478` — peri filter driven by `disable_filter_mem`; `disable_filter_peri` is dead.**
8. **`sce_sec.sv:62,73,74` vs `vexsys.sv:166` — `AMBAID4_VEXD (0x4)` vs `AMBAID4_VEXP (0xD)`.** The Vex is never recognised by the SCE's coreuser capture or `ahben` gate.
9. **`rrc.sv:778` + `rrc.sv:274` — `code_access_error` is gated by `rrccr[12]`, reset `0`.** ReRAM code-region protection is off from reset until software writes `0x4000_0000` (which then force-sets bit 12 via `rrc.sv:1258`).
10. **`sensorc.sv:93` — `cr_vdmask1` (6-bit) used as a scalar ternary condition, IV all-ones.** Voltage-tamper→reset is disabled at reset and is all-or-nothing.
11. **`sce_sec.sv:72` (`mode_non ⇒ ahben=1`) + `sce.sv:60-64` — the SCE crypto RAM (LKEY/KEY/SKEY/SCRT/AKEY/PKB segments) is directly readable at `0x4002_0000` with no access control while `scemode == 0`**; and `sce.sv:370 acenable = mode_sec` disables the internal channel rules in the same state.
12. **`sce.sv:298` — `sce_ts` reset is `sysresetn`, not `sceresetn`.** `truststate` (which authorizes ReRAM key-slot access, `rrc.sv:717`) survives `ar_reset` and `modequit`.
13. **`sce_sec.sv:123` — `ts = {1'b1, tsreg}`.** `trustkey[255]` is permanently 1; a slot with `akeyid == 0xFF` bypasses the trustkey gate.
14. **`rrc.sv:722` — `data_access_error_pre` compares against `userid_k` (key-slot owner) while the rest of the expression uses `userid_d`.** Likely a copy-paste; the data-slot owner check may be reading the wrong ACRAM field.
15. **`rng_top.v:79-140` — `healthtest_err` is a pure status output; it never gates `rngcore_dataout_vld` or `postprocess`.** Plus `trng.sv:283-284` `` `theregrn( intr ) <= '0; `` / `` `theregrn( err ) <= '0; `` — the TRNG never raises an interrupt or error.
16. **`data_buf.v:67-77` + `trng.sv:278` — in DRNG mode the 256-bit seed buffer is written directly over APB (`sfr_buf @0x30`), and `cr_drng_en`/`chaincut`/`cr_anaen` are unlocked CRs (`trng.sv:52,108,131,257-264`).** Software can make the "TRNG" fully deterministic and attacker-chosen.
17. **`rrc.sv:286` — `0x4000_00F0 <= 0x2468` triggers ReRAM suicide, `sfrlock(1'b0)`, no coreuser check**, reachable by CM7-P, Vex-P, MDMA and BDMA-AHB.
18. **`rrc.sv:583` `hresp = 2'h0` + `:555-558` zero-fill** — access-control denials are silent (OKAY, data 0), and `rrccr[15]` (NMI) is 0 at reset.
19. **`cm7sys.sv:761,776` — "everything not boot0/boot1/fw0 is fw1", and `coreuser` updates only on the exact `coreuser_keepcnthit` cycle**, giving a `filtercyc+2`-cycle stale-identity window at every region transition (`coreuser_filtercyc` itself resets to 0, `soc_coresub.sv:274`).
20. **`ao_sysctrl.sv:285-286` + `soc_top.sv:928` — the IPT JTAG TAP owns the PMU voltage/current trims whenever the chip is not in USER mode**, a direct voltage-glitch primitive.
21. **`rbist_wrp.sv:161` + `soc_top.sv:968` — `0x4004_5000` lets any master rewrite the timing trims of all 28 RAM groups including the SCE key RAMs and the RRC ACRAM**, with no lock.
22. **`scedma_amba.sv:305,384,400 / scedma.sv:193,239` — the SCE DMA has no address whitelist and software chooses both the address and `AxPROT`**, while `rrc.sv:681-682` derives `sce_exc_op`/`sce_sec_op` from exactly that software-chosen `AxPROT[0]`.
23. **`qfc.sv:202` — the XIP AES key is a plain unlocked APB CR at `0x4001_0040`** (write-only on read-back, but freely rewritable), and `qfc_aes.sv:16-58` is a pure AXI pass-through with no crypto (the real cipher is inside the closed `sdvt_spi_master_core`).
24. **`rrc.sv:663` — stray double `&`: `axis.awvalid & & axis.awready & clken`.** Parses as `awvalid & (&awready) & clken`; benign for 1-bit but flags the line for review.
25. **`ahb_demux.sv:119-122` — no default slave; unmapped accesses complete with OKAY and read as 0**, so a mis-decoded or filtered-away transaction is indistinguishable from a legitimate one.