/*
	AMD Memory Tweak by
	Elio VP                 <elio@eliovp.be>
	A. Solodovnikov
	Copyright (c) 2019 Eliovp, BVBA. All rights reserved.
	Permission is hereby granted, free of charge, to any person obtaining a copy
	of this software and associated documentation files (the "Software"), to deal
	in the Software without restriction, including without limitation the rights
	to use, copy, modify, merge, publish, distribute and/or sublicense
	copies of the Software, and to permit persons to whom the Software is
	furnished to do so, subject to the following conditions:
	The above copyright notice and this permission notice shall be included in
	all copies or substantial portions of the Software.
	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
	OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
	THE SOFTWARE.
*/

#include <sstream>
#include <iostream>
#include <string.h> // strcasecmp
#include <stdlib.h> // strtoul
#include <stdio.h> // printf
#include <errno.h>
#include <time.h> // nanosleep
#include <sys/mman.h> // mmap
#include <unistd.h> // close lseek read write
#include <fcntl.h> // open
#include <dirent.h> // opendir readdir closedir

extern "C" {
#include "pci/pci.h" // full path /usr/local/include/pci/pci.h
}

#ifndef _countof
#define _countof(a) (sizeof(a)/sizeof(*(a)))
#endif

// from /include/linux/pci_ids.h
#define PCI_VENDOR_ID_AMD 0x1022
#define PCI_VENDOR_ID_ATI 0x1002

#define VERSION "AMD Memory Tweak Linux CLI version 0.1.9\n"

bool IsAmdDisplayDevice(struct pci_dev* dev)
{
	if ((dev->device_class >> 8) == PCI_BASE_CLASS_DISPLAY)
	{
		u8 headerType = pci_read_byte(dev, PCI_HEADER_TYPE);
		if ((headerType & 0x7F) == PCI_HEADER_TYPE_NORMAL)
		{
			if ((dev->vendor_id == PCI_VENDOR_ID_ATI) ||
				(dev->vendor_id == PCI_VENDOR_ID_AMD))
			{
				return true;
			}
		}
	}
	return false;
}

bool IsRelevantDeviceID(struct pci_dev* dev)
{
	return
		(dev->device_id == 0x66a1) || // Vega 20 [Radeon Instinct MI50 32GB]
		(dev->device_id == 0x66af) || // Radeon VII
		(dev->device_id == 0x687f) || // Vega 10 XL/XT [Radeon RX Vega 56/64]
		(dev->device_id == 0x6867) || // Vega 10 XL [Radeon Pro Vega 56]
		(dev->device_id == 0x6863) || // Vega 10 XTX [Radeon Vega Frontier Edition]
		(dev->device_id == 0x67df) || // Ellesmere [Radeon RX 470/480/570/570X/580/580X/590]
		(dev->device_id == 0x67c4) || // Ellesmere [Radeon Pro WX 7100]
		(dev->device_id == 0x67c7) || // Ellesmere [Radeon Pro WX 5100]
		(dev->device_id == 0x67ef) || // Baffin [Radeon RX 460/560D / Pro 450/455/460/555/555X/560/560X]
		(dev->device_id == 0x67ff) || // Baffin [Radeon RX 550 640SP / RX 560/560X]
		(dev->device_id == 0x7300) || // Fiji [Radeon R9 FURY / NANO Series]
		(dev->device_id == 0x67b0) || // Hawaii XT / Grenada XT [Radeon R9 290X/390X]
		(dev->device_id == 0x67b1) || // Hawaii PRO [Radeon R9 290/390]
		(dev->device_id == 0x6798) || // Tahiti XT [Radeon HD 7970/8970 OEM / R9 280X]
		(dev->device_id == 0x679a); // Tahiti PRO [Radeon HD 7950/8950 OEM / R9 280]
}

static bool IsR9(struct pci_dev* dev)
{
	return
		(dev->device_id == 0x67b0) || // Hawaii XT / Grenada XT [Radeon R9 290X/390X]
		(dev->device_id == 0x67b1) || // Hawaii PRO [Radeon R9 290/390]
		(dev->device_id == 0x6798) || // Tahiti XT [Radeon HD 7970/8970 OEM / R9 280X]
		(dev->device_id == 0x679a); // Tahiti PRO [Radeon HD 7950/8950 OEM / R9 280]
}

typedef enum { GDDR5, HBM, HBM2 } MemoryType;

static MemoryType DetermineMemoryType(struct pci_dev* dev)
{
	struct {
		u16 vendor_id;
		u16 device_id;
		MemoryType memory_type;
	} KnownGPUs[] = {
		/* Vega20 - Radeon VII */
		{ 0x1002, 0x66a0, HBM2 }, // "Radeon Instinct", CHIP_VEGA20
		{ 0x1002, 0x66a1, HBM2 }, // "Radeon Vega20", CHIP_VEGA20
		{ 0x1002, 0x66a2, HBM2 }, // "Radeon Vega20", CHIP_VEGA20
		{ 0x1002, 0x66a3, HBM2 }, // "Radeon Vega20", CHIP_VEGA20
		{ 0x1002, 0x66a4, HBM2 }, // "Radeon Vega20", CHIP_VEGA20
		{ 0x1002, 0x66a7, HBM2 }, // "Radeon Pro Vega20", CHIP_VEGA20
		{ 0x1002, 0x66af, HBM2 }, // "Radeon Vega20", CHIP_VEGA20
		{ 0x1002, 0x66af, HBM2 }, // "Radeon VII", CHIP_VEGA20
		/* Vega */
		{ 0x1002, 0x687f, HBM2 }, // "Radeon RX Vega 56/64", CHIP_VEGA10
		{ 0x1002, 0x6863, HBM2 }, // "Radeon Vega Frontier Edition", CHIP_VEGA10
		/* Fury/Nano */
		{ 0x1002, 0x7300, HBM }, // "Radeon R9 Fury/Nano/X", CHIP_FIJI
	};
	for (int i = 0; i < _countof(KnownGPUs); i++)
	{
		if ((KnownGPUs[i].vendor_id == dev->vendor_id) && (KnownGPUs[i].device_id == dev->device_id))
		{
			return KnownGPUs[i].memory_type;
		}
	}
	return GDDR5;
}

#define AMD_TIMING_REGS_BASE_1 0x50200
#define AMD_TIMING_REGS_BASE_2 0x52200
#define AMD_TIMING_REGS_BASE_3 0x54200
#define AMD_TIMING_REGS_BASE_4 0x56200

typedef union {
	u32 value;
	struct {
		u32 /*Reserved*/ : 8;
		u32 MAN : 4;
		u32 VEN : 4;
		u32 : 16;
	} rx;
	struct {
		u32 /*Reserved*/ : 24;
		u32 MAN : 8;
	} hbm;
} MANUFACTURER;
#define MANUFACTURER_ID 0x2A00
#define MANUFACTURER_ID_HBM 0x29C4
#define MANUFACTURER_ID_HBM2 0x5713C

typedef struct {
	u32 frequency;
	// TIMING1
	u32 CL : 8;
	u32 RAS : 8;
	u32 RCDRD : 8;
	u32 RCDWR : 8;
	// TIMING2
	u32 RCAb : 8;
	u32 RCPb : 8;
	u32 RPAb : 8;
	u32 RPPb : 8;
	// TIMING3
	u32 RRDS : 8;
	u32 RRDL : 8;
	u32 /*Reserved*/ : 8;
	u32 RTP : 8;
	// TIMING4
	u32 FAW : 8;
	u32 /*Reserved*/ : 24;
	// TIMING5
	u32 CWL : 8;
	u32 WTRS : 8;
	u32 WTRL : 8;
	u32 /*Reserved*/ : 8;
	// TIMING6
	u32 WR : 8;
	u32 /*Reserved*/ : 24;
	// TIMING7
	u32 /*Reserved*/ : 8;
	u32 RREFD : 8;
	u32 /*Reserved*/ : 8;
	u32 /*Reserved*/ : 8;
	// TIMING8
	u32 RDRDDD : 8;
	u32 RDRDSD : 8;
	u32 RDRDSC : 8;
	u32 RDRDSCL : 6;
	u32 /*Reserved*/ : 2;
	// TIMING9
	u32 WRWRDD : 8;
	u32 WRWRSD : 8;
	u32 WRWRSC : 8;
	u32 WRWRSCL : 6;
	u32 /*Reserved*/ : 2;
	// TIMING10
	u32 WRRD : 8;
	u32 RDWR : 8;
	u32 /*Reserved*/ : 16;
	// PADDING
	u32 /*Reserved*/ : 32;
	// TIMING12
	u32 REF : 16;		// Determines at what rate refreshes will be executed. Vega RXboost :p
	u32 /*Reserved*/ : 16;
	// TIMING13
	u32 MRD : 8;
	u32 MOD : 8;
	u32 /*Reserved*/ : 16;
	// TIMING14
	u32 XS : 16;		// self refresh exit period
	u32 /*Reserved*/ : 16;
	// PADDING
	u32 /*Reserved*/ : 32;
	// TIMING16
	u32 XSMRS : 16;
	u32 /*Reserved*/ : 16;
	// TIMING17
	u32 PD : 4;
	u32 CKSRE : 6;
	u32 CKSRX : 6;
	u32 /*Reserved*/ : 16;
	// PADDING
	u32 /*Reserved*/ : 32;
	// PADDING
	u32 /*Reserved*/ : 32;
	// TIMING20
	u32 RFCPB : 16;
	u32 STAG : 8;
	u32 /*Reserved*/ : 8;
	// TIMING21
	u32 XP : 8;
	u32 /*Reserved*/ : 8;
	u32 CPDED : 8;
	u32 CKE : 8;
	// TIMING22
	u32 RDDATA : 8;
	u32 WRLAT : 8;
	u32 RDLAT : 8;
	u32 WRDATA : 4;
	u32 /*Reserved*/ : 4;
	// TIMING23
	u32 /*Reserved*/ : 16;
	u32 CKESTAG : 8;
	u32 /*Reserved*/ : 8;
	// RFC
	u32 RFC : 16;
	u32 /*Reserved*/ : 16;
} HBM2_TIMINGS;

typedef union {
	u32 value;
	struct {
		u32 DAT_DLY : 4;		// Data output latency
		u32 DQS_DLY : 4;		// DQS Latency
		u32 DQS_XTR : 1;		// Write Preamble (ON/OFF)
		u32 DAT_2Y_DLY : 1;		// Delay data (QDR Mode!) (ON/OFF)
		u32 ADR_2Y_DLY : 1;		// Delay addr (QDR Mode!) (ON/OFF)
		u32 CMD_2Y_DLY : 1;		// Delay cmd (QDR Mode!) (ON/OFF)
		u32 OEN_DLY : 4;		// Write cmd enable Latency
		u32 OEN_EXT : 4;		// Output enable -> Data Burst (0 - 8 where 1 = 1 cycle, 5 = 5 cycles..)
		u32 OEN_SEL : 2;
		u32 /*Reserved*/ : 2;
		u32 ODT_DLY : 4;		// On-Die-Termination latency
		u32 ODT_EXT : 1;		// On-Die-Termination enable after burst
		u32 ADR_DLY : 1;
		u32 CMD_DLY : 1;
		u32 /*Reserved*/ : 1;
	} rx;
	struct {
		u32 DAT_DLY : 5;		// Data output latency
		u32 DQS_DLY : 5;		// DQS Latency
		u32 DQS_XTR : 1;		// Write Preamble (ON/OFF)
		u32 OEN_DLY : 5;		// Write cmd enable Latency
		u32 OEN_EXT : 4;		// Output enable -> Data Burst (0 - 8 where 1 = 1 cycle, 5 = 5 cycles..)
		u32 OEN_SEL : 2;
		u32 CMD_DLY : 1;
		u32 ADR_DLY : 1;
		u32 /*Reserved*/ : 8;
	} hbm;
} SEQ_WR_CTL_D0;
#define MC_SEQ_WR_CTL_D0 0x28bc // Chan 0 write commands
#define MC_SEQ_WR_CTL_D0_HBM 0x28EC

typedef union {
	u32 value;
	struct {
		u32 DAT_DLY : 4;		// Data output latency
		u32 DQS_DLY : 4;		// DQS Latency
		u32 DQS_XTR : 1;		// Write Preamble (ON/OFF)
		u32 DAT_2Y_DLY : 1;		// Delay data (QDR Mode!) (ON/OFF)
		u32 ADR_2Y_DLY : 1;		// Delay addr (QDR Mode!) (ON/OFF)
		u32 CMD_2Y_DLY : 1;		// Delay cmd (QDR Mode!) (ON/OFF)
		u32 OEN_DLY : 4;		// Write cmd enable Latency
		u32 OEN_EXT : 4;		// Output enable -> Data Burst (0 - 8 where 1 = 1 cycle, 5 = 5 cycles..)
		u32 OEN_SEL : 2;
		u32 /*Reserved*/ : 2;
		u32 ODT_DLY : 4;		// On-Die-Termination latency
		u32 ODT_EXT : 1;		// On-Die-Termination enable after burst
		u32 ADR_DLY : 1;
		u32 CMD_DLY : 1;
		u32 : 1;
	} rx;
	struct {
		u32 DAT_DLY : 5;		// Data output latency
		u32 DQS_DLY : 5;		// DQS Latency
		u32 DQS_XTR : 1;		// Write Preamble (ON/OFF)
		u32 OEN_DLY : 5;		// Write cmd enable Latency
		u32 OEN_EXT : 4;		// Output enable -> Data Burst (0 - 8 where 1 = 1 cycle, 5 = 5 cycles..)
		u32 OEN_SEL : 2;
		u32 CMD_DLY : 1;
		u32 ADR_DLY : 1;
		u32 /*Reserved*/ : 8;
	} hbm;
} SEQ_WR_CTL_D1;
#define MC_SEQ_WR_CTL_D1 0x28c0 // Chan 1 write commands
#define MC_SEQ_WR_CTL_D1_HBM 0x28F4

typedef union {
	u32 value;
	struct {
		u32 DAT_DLY : 5;		// Data output latency
		u32 DQS_DLY : 5;		// DQS Latency
		u32 DQS_XTR : 1;		// Write Preamble (ON/OFF)
		u32 OEN_DLY : 5;		// Write cmd enable Latency
		u32 OEN_EXT : 4;		// Output enable -> Data Burst (0 - 8 where 1 = 1 cycle, 5 = 5 cycles..)
		u32 OEN_SEL : 2;
		u32 CMD_DLY : 1;
		u32 ADR_DLY : 1;
		u32 /*Reserved*/ : 8;
	};
} SEQ_WR_CTL_D2;
#define MC_SEQ_WR_CTL_D2_HBM 0x28FC

typedef union {
	u32 value;
	struct {
		u32 DAT_DLY : 5;		// Data output latency
		u32 DQS_DLY : 5;		// DQS Latency
		u32 DQS_XTR : 1;		// Write Preamble (ON/OFF)
		u32 OEN_DLY : 5;		// Write cmd enable Latency
		u32 OEN_EXT : 4;		// Output enable -> Data Burst (0 - 8 where 1 = 1 cycle, 5 = 5 cycles..)
		u32 OEN_SEL : 2;
		u32 CMD_DLY : 1;
		u32 ADR_DLY : 1;
		u32 /*Reserved*/ : 8;
	};
} SEQ_WR_CTL_D3;
#define MC_SEQ_WR_CTL_D3_HBM 0x2904

typedef union {
	u32 value;
	struct {
		u32 THRESH : 3;			// Threshold
		u32 /*Reserved*/ : 1;
		u32 LEVEL : 3;			// Level
		u32 PWRDOWN : 1;		// PWRDOWN
		u32 SHUTDOWN : 3;		// SHUTDOWN
		u32 EN_SHUTDOWN : 1;	// EN_SHUTDOWN
		u32 OVERSAMPLE : 2;
		u32 AVG_SAMPLE : 1;
		u32 /*Reserved*/ : 17;
	};
} THERMAL_THROTTLE;
#define MC_THERMAL_THROTTLE 0x2ACC // Thermal Throttle Control

typedef union {
	u32 value;
	struct {
		u32 CKSRE : 3;			// Valid clock requirement after CKSRE
		u32 /*Reserved*/ : 1;
		u32 CKSRX : 3;			// Valid clock requirement before CKSRX
		u32 /*Reserved*/ : 1;
		u32 CKE_PULSE : 4;		// Minimum CKE pulse
		u32 CKE : 6;
		u32 SEQ_IDLE : 3;		// idle before deassert rdy to arb
		u32 /*Reserved*/ : 2;
		u32 CKE_PULSE_MSB : 1;	// Minimum CKE pulse msb
		u32 SEQ_IDLE_SS : 8;	// idle before deassert rdy to arb at ss
	} rx;
	struct {
		u32 CKSRE : 3;			// Valid clock requirement after CKSRE
		u32 CKSRX : 3;			// Valid clock requirement before CKSRX
		u32 CKE_PULSE : 5;		// Minimum CKE pulse
		u32 CKE : 8;
		u32 SEQ_IDLE : 3;		// idle before deassert rdy to arb
		u32 SEQ_IDLE_SS : 8;	// idle before deassert rdy to arb at ss
		u32 /*Reserved*/ : 2;
	} hbm;
} SEQ_PMG_TIMING;
#define MC_SEQ_PMG_TIMING 0x28B0 // Power Management
#define MC_SEQ_PMG_TIMING_HBM 0x28C4 // Power Management

typedef union {
	u32 value;
	struct {
		u32 RCDW : 5;			// # of cycles from active to write
		u32 RCDWA : 5;			// # of cycles from active to write with auto-precharge
		u32 RCDR : 5;			// # of cycles from active to read
		u32 RCDRA : 5;			// # of cycles from active to read with auto-precharge
		u32 RRD : 4;			// # of cycles from active bank a to active bank b
		u32 RC : 7;				// # of cycles from active to active/auto refresh
		u32 /*Reserved*/ : 1;
	};
} SEQ_RAS_TIMING;
#define MC_SEQ_RAS_TIMING 0x28A0
#define MC_SEQ_RAS_TIMING_HBM 0x28A4

typedef union {
	u32 value;
	struct {
		u32 NOPW : 2;			// Extra cycle(s) between successive write bursts
		u32 NOPR : 2;			// Extra cycle(s) between successive read bursts
		u32 R2W : 5;			// Read to write turn around time
		u32 CCDL : 3;			// Cycles between r/w from bank A to r/w bank B
		u32 R2R : 4;			// Read to read time
		u32 W2R : 5;			// Write to read turn around time
		u32 /*Reserved*/ : 3;
		u32 CL : 5;				// CAS to data return latency (0 - 20)
		u32 /*Reserved*/ : 3;
	} rx;
	struct {
		u32 NOPW : 2;			// Extra cycle(s) between successive write bursts
		u32 NOPR : 2;			// Extra cycle(s) between successive read bursts
		u32 R2W : 5;			// Read to write turn
		u32 CCDL : 3;			// Cycles between r/w from bank A to r/w bank B
		u32 R2R : 4;			// Read to read time
		u32 W2R : 5;			// Write to read turn
		u32 CL : 5;				// CAS to data return latency
		u32 /*Reserved*/ : 6;
	} hbm;
} SEQ_CAS_TIMING;
#define MC_SEQ_CAS_TIMING 0x28A4
#define MC_SEQ_CAS_TIMING_HBM 0x28AC

typedef union {
	u32 value;
	struct {
		u32 RP_WRA : 6;			// From write with auto-precharge to active
		u32 /*Reserved*/ : 2;
		u32 RP_RDA : 6;			// From read with auto-precharge to active
		u32 /*Reserved*/ : 1;
		u32 TRP : 5;			// Precharge command period
		u32 RFC : 9;			// Auto-refresh command period
		u32 /*Reserved*/ : 3;
	} rx;
	struct {
		u32 RP_WRA : 8;			// From write with auto-precharge to active
		u32 RP_RDA : 7;			// From read with auto-precharge to active
		u32 TRP : 5;			// Precharge command period
		u32 RFC : 9;			// Auto-refresh command period
		u32 /*Reserved*/ : 3;
	} r9;
	struct {
		u32 RP_WRA : 6;			// From write with auto-precharge to active
		u32 RP_RDA : 6;			// From read with auto-precharge to active
		u32 TRP : 5;			// Precharge command period
		u32 RFC : 7;			// Auto-refresh command period
		u32 RRDL : 4;
		u32 MRD : 4;
	} hbm;
} SEQ_MISC_TIMING;
#define MC_SEQ_MISC_TIMING 0x28A8
#define MC_SEQ_MISC_TIMING_HBM 0x28B4

typedef union {
	u32 value;
	struct {
		u32 PA2RDATA : 3;       // DDR4
		u32 /*Reserved*/ : 1;
		u32 PA2WDATA : 3;       // DDR4
		u32 /*Reserved*/ : 1;
		u32 FAW : 5;            // The time window in wich four activates are allowed in the same rank
		u32 REDC : 3;           // Min 0, Max 7
		u32 WEDC : 5;           // Min 0, Max 7
		u32 T32AW : 4;          // Max 12
		u32 /*Reserved*/ : 3;
		u32 WDATATR : 4;        // WCMD timing for write training
	} rx;
	struct {
		u32 PA2RDATA : 3;
		u32 PA2WDATA : 3;
		u32 FAW : 5;            // The time window in wich four activates are allowed in the same rank
		u32 WPAR : 3;
		u32 RPAR : 3;
		u32 T32AW : 4;
		u32 WDATATR : 4;
		u32 /*Reserved*/ : 7;
	} hbm;
} SEQ_MISC_TIMING2;
#define MC_SEQ_MISC_TIMING2 0x28AC
#define MC_SEQ_MISC_TIMING2_HBM 0x28BC

// Mode Registers (JESD212 for more info)
typedef union {
	u32 value;
	struct {
		// MR0
		u32 WL : 3;				// Write Latency
		u32 CL : 4;				// CAS Latency 
		u32 TM : 1;
		u32 WR : 4;				// Write Recovery
		u32 BA0 : 1;
		u32 BA1 : 1;
		u32 BA2 : 1;
		u32 BA3 : 1;
		// MR1
		u32 DS : 2;				// Driver Strength (0 = Auto Calibration)
		u32 DT : 2;				// Data Termination (0 = Disabled)
		u32 ADR : 2;				// ADR CMD Termination (0 = CKE value at Reset)
		u32 CAL : 1;			// Calibration Update
		u32 PLL : 1;
		u32 RDBI : 1;			// Read DBI (ON/OFF)
		u32 WDBI : 1;			// Write DBI (ON/OFF)
		u32 ABI : 1;			// (ON/OFF)
		u32 RESET : 1;			// PLL Reset
		u32 BA_0 : 1;
		u32 BA_1 : 1;
		u32 BA_2 : 1;
		u32 BA_3 : 1;
	} rx;
	struct {
		// MR0
		u32 DBR : 1;			// Read DBIac (OFF/ON)
		u32 DBW : 1;			// Write DBIac (OFF/ON)
		u32 TCSR : 1;			// Temperature Compensated Self Refresh (OFF/ON)
		u32 /*Reserved*/ : 1;
		u32 DQR : 1;			// DQ Bus Read Parity (OFF/ON)
		u32 DQW : 1;			// DQ Bus Write Parity (OFF/ON)
		u32 ADD_PAR : 1;		// Address, Command Bus Parity for Row, Column Bus (OFF/ON)
		u32 TM : 1;				// Vendor Specific (NORMAL/TEST)
		// MR1
		u32 WR : 5;				// Write Recovery
		u32 NDS : 3;			// Nominal Driver Strength
		// MR2
		u32 WL : 3;				// Write Latency
		u32 RL : 5;				// Read Latency
		// MR3
		u32 APRAS : 6;			// Activate to Precharge RAS
		u32 BG : 1;				// Bank Group
		u32 BL : 1;				// Burst Length
	} hbm;
} SEQ_MISC1;
#define MC_SEC_MISC1 0x2A04
#define MC_SEC_MISC1_HBM 0x29C8 // Beta (untested)

typedef union {
	u32 value;
	struct {
		// MR2
		u32 OCD_DWN : 3;		// OCD Pulldown Driver Offset
		u32 OCD_UP : 3;			// OCD Pullup Driver Offset
		u32 WCK : 3;			// Data and WCK Termination Offset
		u32 ADR : 3;			// ADR/CMD Termination Offset
		u32 BA0 : 1;
		u32 BA1 : 1;
		u32 BA2 : 1;
		u32 BA3 : 1;
		// MR3
		u32 SR : 2;				// Self Refresh (0 = 32ms)
		u32 WCK01 : 1;			// (OFF/ON)
		u32 WCK23 : 1;			// (OFF/ON)
		u32 WCK2CK : 1;			// (OFF/ON)
		u32 RDQS : 1;			// (OFF/ON)
		u32 INFO : 2;			// Dram Info (0=Off)
		u32 WCK2 : 2;			// WCK Termination
		u32 BG : 2;				// Bank Groups
		u32 BA_0 : 1;
		u32 BA_1 : 1;
		u32 BA_2 : 1;
		u32 BA_3 : 1;
	};
} SEQ_MISC2;
#define MC_SEC_MISC2 0x2A08

typedef union {
	u32 value;
	struct {
		// MR4
		u32 EDCHP : 4;			// EDC Hold Pattern
		u32 CRCWL : 3;			// CRC Write Latency
		u32 CRCRL : 2;			// CRC Read Latency
		u32 RDCRC : 1;			// (ON/OFF)
		u32 WRCRC : 1;			// (ON/OFF)
		u32 EDC : 1;			// (OFF/ON)
		u32 BA0 : 1;
		u32 BA1 : 1;
		u32 BA2 : 1;
		u32 BA3 : 1;
		// MR5
		u32 LP1 : 1;			// (OFF/ON)
		u32 LP2 : 1;			// (OFF/ON)
		u32 LP3 : 1;			// (OFF/ON)
		u32 PLL : 3;			// PLL/DLL Band-Width (0 = Vendor Specific)
		u32 RAS : 6;
		u32 BA_0 : 1;
		u32 BA_1 : 1;
		u32 BA_2 : 1;
		u32 BA_3 : 1;
	};
} SEQ_MISC3;
#define MC_SEC_MISC3 0x2A2C

typedef union {
	u32 value;
	struct {
		// MR6
		u32 WCK : 1;			// WCK2CK Pin
		u32 VREFD_M : 1;		// VREFD Merge
		u32 A_VREFD : 1;		// Auto VREFD Training
		u32 VREFD : 1;
		u32 VREFD_O : 4;		// Offset rows M-U
		u32 VREFD_0_2 : 4;		// Offset rows A-F
		u32 BA0 : 1;
		u32 BA1 : 1;
		u32 BA2 : 1;
		u32 BA3 : 1;
		// MR7
		u32 PLL_STD : 1;		// PLL Standby (OFF/ON)
		u32 PLL_FL : 1;			// PLL Fast Lock (OFF/ON)
		u32 PLL_DEL : 1;		// PLL Delay Compensation (OFF/ON)
		u32 LF_MOD : 1;			// Low Frequency Mode (OFF/ON)
		u32 AUTO : 1;			// WCK2CK Auto Sync (OFF/ON)
		u32 DQ : 1;				// DQ Preamble (OFF/ON)
		u32 TEMP : 1;			// Temp Sensor (OFF/ON)
		u32 HALF : 1;			// Half VREFD
		u32 VDD_R : 2;			// VDD Range
		u32 RFU : 2;
		u32 BA_0 : 1;
		u32 BA_1 : 1;
		u32 BA_2 : 1;
		u32 BA_3 : 1;
	};
} SEQ_MISC4;
#define MC_SEC_MISC4 0x2A30

typedef union {
	u32 value;
	struct {
		// MR15
		u32 /*Reserved*/ : 8;
		u32 MRE0 : 1;			// Mode Register 0-14 Enable MF=0 (ON/OFF)
		u32 MRE1 : 1;			// Mode Register 0-14 Enable MF=1 (ON/OFF)
		u32 ADT : 1;			// Address Training (OFF/ON)
		u32 RFU : 1;
		u32 BA0 : 1;
		u32 BA1 : 1;
		u32 BA2 : 1;
		u32 BA3 : 1;
		u32 /*Reserved*/ : 16;
	};
} SEQ_MISC7;
#define MC_SEC_MISC7 0x2A64

typedef union {
	u32 value;
	struct {
		// MR8
		u32 CLEHF : 1;			// Cas Latency Extra High Frequency (0 = normal range, 1 = Extended)
		u32 WREHF : 1;			// Write Recovery Extra High Frequency (0 = normal range, 1 = Extended)
		u32 RFU : 10;
		u32 BA0 : 1;
		u32 BA1 : 1;
		u32 BA2 : 1;
		u32 BA3 : 1;
		u32 /*Reserved*/ : 16;
	};
} SEQ_MISC8;
#define MC_SEC_MISC8 0x297C

typedef union {
	u32 value;
	struct {
		u32 ACTRD : 8;
		u32 ACTWR : 8;
		u32 RASMACTRD : 8;
		u32 RASMACTWR : 8;
	};
} ARB_DRAM_TIMING;
#define MC_ARB_DRAM_TIMING 0x2774

typedef union {
	u32 value;
	struct {
		u32 RAS2RAS : 8;
		u32 RP : 8;
		u32 WRPLUSRP : 8;
		u32 BUS_TURN : 8;
	};
} ARB_DRAM_TIMING2;
#define MC_ARB_DRAM_TIMING2 0x2778

typedef union {
	u32 value;
	struct {
		u32 REF : 16;
		u32 /*Reserved*/ : 16;
	};
} ARB_RFSH_RATE;
#define MC_ARB_RFSH_RATE 0x27b0 // The famous RXBoost :p

typedef union {
	u32 value;
	struct {
		u32 TWT2RT : 5;			// # of cycles from write to read train command
		u32 TARF2T : 5;			// # of cycles from auto refresh to train command
		u32 TT2ROW : 5;			// # of cycles between row charge command
		u32 TLD2LD : 5;			// # of cycles between LDFF command
		u32 /*Reserved*/ : 12;
	};
} SEQ_TRAINING;
#define MC_SEQ_TRAINING 0x2900

typedef union {
	u32 value;
	struct {
		u32 ENB : 1;
		u32 CNT : 5;
		u32 TRC : 16;
		u32 /*Reserved*/ : 10;
	};
} SEQ_ROW_HAMMER;
#define MC_SEQ_ROW_HAMMER 0x27b0

static u64 ParseIndicesArg(const char* arg)
{
	u64 mask = 0;
	std::istringstream ss(arg);
	while (!ss.eof())
	{
		std::string token;
		std::getline(ss, token, ',');
		unsigned long index = strtoul(token.c_str(), 0, 10);
		if ((errno == EINVAL) || (errno == ERANGE) || (index >= 64))
		{
			std::cout << "Invalid GPU index specified.\n";
			return 1;
		}
		mask |= ((u64)1 << index);
	}
	return mask;
}

static bool ParseNumericArg(int argc, const char* argv[], int& i, const char* arg, u32 & value)
{
	if (!strcasecmp(arg, argv[i]))
	{
		if (i == (argc - 1))
		{
			std::cout << "Argument \"" << argv[i] << "\" requires a parameter.\n";
			exit(1);
		}
		i++;
		value = strtoul(argv[i], 0, 10);
		if ((errno == EINVAL) || (errno == ERANGE))
		{
			std::cout << "Failed to parse parameter " << argv[i - 1] << " " << argv[i] << "\n";
			exit(1);
		}
		return true;
	}
	return false;
}

static int pci_find_instance(char* pci_string)
{
	DIR* dir = opendir("/sys/kernel/debug/dri");
	if (!dir)
	{
		perror("Couldn't open DRI under debugfs\n");
		return -1;
	}

	struct dirent* entry;
	while (entry = readdir(dir))
	{
		if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;

		char name[300];
		snprintf(name, sizeof(name) - 1, "/sys/kernel/debug/dri/%s/name", entry->d_name);
		FILE * f = fopen(name, "r");
		if (!f) continue;

		char device[256];
		device[sizeof(device) - 1] = 0;
		int parsed_device = fscanf(f, "%*s %255s", device);
		fclose(f);

		if (parsed_device != 1) continue;

		// strip off dev= for kernels > 4.7
		if (strstr(device, "dev="))
		{
			memmove(device, device + 4, strlen(device) - 3);
		}

		if (!strcmp(pci_string, device))
		{
			closedir(dir);
			return atoi(entry->d_name);
		}
	}
	closedir(dir);
	return -1;
}

typedef struct {
	struct pci_dev* dev;
	int mmio;

	char log[1000];
	bool modify[25];
	MANUFACTURER man;
	// HBM2
	HBM2_TIMINGS hbm2;
	// GDDR5 && HBM1
	SEQ_WR_CTL_D0 ctl1;
	SEQ_WR_CTL_D1 ctl2;
	SEQ_PMG_TIMING pmg;
	SEQ_RAS_TIMING ras;
	SEQ_CAS_TIMING cas;
	SEQ_MISC_TIMING misc;
	SEQ_MISC_TIMING2 misc2;
	SEQ_MISC1 smisc1;
	SEQ_MISC2 smisc2;
	SEQ_MISC3 smisc3;
	SEQ_MISC4 smisc4;
	SEQ_MISC7 smisc7;
	SEQ_MISC8 smisc8;
	ARB_DRAM_TIMING dram1;
	ARB_DRAM_TIMING2 dram2;
	ARB_RFSH_RATE ref;
	SEQ_TRAINING train;
	// HBM1 Specific
	SEQ_ROW_HAMMER ham;
	THERMAL_THROTTLE throt;
	SEQ_WR_CTL_D2 ctl3;
	SEQ_WR_CTL_D3 ctl4;
} GPU;

static u32 ReadMMIODword(long address, GPU * gpu)
{
	u32 value;
	lseek(gpu->mmio, address, SEEK_SET);
	read(gpu->mmio, &value, sizeof(u32));
	return value;
}

static int gpu_compare(const void* A, const void* B)
{
	const struct pci_dev* a = ((const GPU*)A)->dev;
	const struct pci_dev* b = ((const GPU*)B)->dev;
	if (a->domain < b->domain) return -1;
	if (a->domain > b->domain) return 1;
	if (a->bus < b->bus) return -1;
	if (a->bus > b->bus) return 1;
	if (a->dev < b->dev) return -1;
	if (a->dev > b->dev) return 1;
	if (a->func < b->func) return -1;
	if (a->func > b->func) return 1;
	return 0;
}

static void PrintCurrentValues(GPU * gpu)
{
	fprintf(stdout, "pci:%04x:%02x:%02x.%d\n", gpu->dev->domain, gpu->dev->bus, gpu->dev->dev, gpu->dev->func);
	fflush(stdout);
	if (DetermineMemoryType(gpu->dev) == HBM2)
	{
		HBM2_TIMINGS current = gpu->hbm2;
		MANUFACTURER man = gpu->man;
		std::cout << "Memory state: " << std::dec;
		std::cout <<
			((current.frequency == 0x118) ? "800MHz" :
			(current.frequency == 0x11C) ? "1000MHz" :
				(current.frequency == 0x11E) ? "1200MHz" : "Unknown") << std::endl;
		std::cout << "Memory: " << std::dec;
		std::cout <<
			((man.hbm.MAN == 0x63) ? "Hynix HBM2" :
			(man.hbm.MAN == 0x61) ? "Samsung HBM2" : "Unknown") << std::endl;
		std::cout << "Timing 1:\t";
		std::cout << "  CL: " << current.CL << "\t";
		std::cout << "  RAS: " << current.RAS << "\t";
		std::cout << "  RCDRD: " << current.RCDRD << "\t";
		std::cout << "  RCDWR: " << current.RCDWR << "\n";
		std::cout << "Timing 2:\t";
		std::cout << "  RCAb (RC): " << current.RCAb << "\t";
		std::cout << "  RCPb (RC): " << current.RCPb << "\t";
		std::cout << "  RPAb (RP): " << current.RPAb << "\t";
		std::cout << "  RPPb (RP): " << current.RPPb << "\n";
		std::cout << "Timing 3:\t";
		std::cout << "  RRDS: " << current.RRDS << "\t";
		std::cout << "  RRDL: " << current.RRDL << "\t";
		std::cout << "  RTP: " << current.RTP << "\n";
		std::cout << "Timing 4:\t";
		std::cout << "  FAW: " << current.FAW << "\n";
		std::cout << "Timing 5:\t";
		std::cout << "  CWL: " << current.CWL << "\t";
		std::cout << "  WTRS: " << current.WTRS << "\t";
		std::cout << "  WTRL: " << current.WTRL << "\n";
		std::cout << "Timing 6:\t";
		std::cout << "  WR: " << current.WR << "\n";
		std::cout << "Timing 7:\t";
		std::cout << "  RREFD: " << current.RREFD << "\n";
		std::cout << "Timing 8:\t";
		std::cout << "  RDRDDD: " << current.RDRDDD << "\t";
		std::cout << "  RDRDSD: " << current.RDRDSD << "\t";
		std::cout << "  RDRDSC: " << current.RDRDSC << "\t";
		std::cout << "  RDRDSCL: " << current.RDRDSCL << "\n";
		std::cout << "Timing 9:\t";
		std::cout << "  WRWRDD: " << current.WRWRDD << "\t";
		std::cout << "  WRWRSD: " << current.WRWRSD << "\t";
		std::cout << "  WRWRSC: " << current.WRWRSC << "\t";
		std::cout << "  WRWRSCL: " << current.WRWRSCL << "\n";
		std::cout << "Timing 10:\t";
		std::cout << "  WRRD: " << current.WRRD << "\t";
		std::cout << "  RDWR: " << current.RDWR << "\n";
		std::cout << "Timing 12:\t";
		std::cout << "  REF: " << current.REF << "\n";
		std::cout << "Timing 13:\t";
		std::cout << "  MRD: " << current.MRD << "\t";
		std::cout << "  MOD: " << current.MOD << "\n";
		std::cout << "Timing 14:\t";
		std::cout << "  XS: " << current.XS << "\n";
		std::cout << "Timing 16:\t";
		std::cout << "  XSMRS: " << current.XSMRS << "\n";
		std::cout << "Timing 17:\t";
		std::cout << "  PD: " << current.PD << "  \t";
		std::cout << "  CKSRE: " << current.CKSRE << "\t";
		std::cout << "  CKSRX: " << current.CKSRX << "\n";
		std::cout << "Timing 20:\t";
		std::cout << "  RFCPB: " << current.RFCPB << "\t";
		std::cout << "  STAG: " << current.STAG << "\n";
		std::cout << "Timing 21:\t";
		std::cout << "  XP: " << current.XP << "  \t";
		std::cout << "  CPDED: " << current.CPDED << "\t";
		std::cout << "  CKE: " << current.CKE << "\n";
		std::cout << "Timing 22:\t";
		std::cout << "  RDDATA: " << current.RDDATA << "\t";
		std::cout << "  WRLAT: " << current.WRLAT << "\t";
		std::cout << "  RDLAT: " << current.RDLAT << "\t";
		std::cout << "  WRDATA: " << current.WRDATA << "\n";
		std::cout << "Timing 23:\t";
		std::cout << "  CKESTAG: " << current.CKESTAG << "\n";
		std::cout << "RFC Timing:\t";
		std::cout << "  RFC: " << current.RFC << "\n";
		std::cout << "\n";
	}
	else if (DetermineMemoryType(gpu->dev) == HBM) {
		MANUFACTURER man = gpu->man;
		printf((man.hbm.MAN == 0x63) ? "   Hynix HBM" :
			(man.hbm.MAN == 0x61) ? "   Samsung HBM" : "   Unknown");
		printf("\n\nChannel 0's write command parameters:\n");
		printf("  \t  DAT_DLY: %d\t", gpu->ctl1.hbm.DAT_DLY);
		printf("  DQS_DLY: %d\t", gpu->ctl1.hbm.DQS_DLY);
		printf("  DQS_XTR: %d\t", gpu->ctl1.hbm.DQS_XTR);
		printf("  OEN_DLY: %d\n", gpu->ctl1.hbm.OEN_DLY);
		printf("  \t  OEN_EXT: %d\t", gpu->ctl1.hbm.OEN_EXT);
		printf("  OEN_SEL: %d\t", gpu->ctl1.hbm.OEN_SEL);
		printf("  CMD_DLY: %d\t", gpu->ctl1.hbm.CMD_DLY);
		printf("  ADR_DLY: %d\n", gpu->ctl1.hbm.ADR_DLY);
		printf("Channel 1's write command parameters:\n");
		printf("  \t  DAT_DLY: %d\t", gpu->ctl2.hbm.DAT_DLY);
		printf("  DQS_DLY: %d\t", gpu->ctl2.hbm.DQS_DLY);
		printf("  DQS_XTR: %d\t", gpu->ctl2.hbm.DQS_XTR);
		printf("  OEN_DLY: %d\n", gpu->ctl2.hbm.OEN_DLY);
		printf("  \t  OEN_EXT: %d\t", gpu->ctl2.hbm.OEN_EXT);
		printf("  OEN_SEL: %d\t", gpu->ctl2.hbm.OEN_SEL);
		printf("  CMD_DLY: %d\t", gpu->ctl2.hbm.CMD_DLY);
		printf("  ADR_DLY: %d\n", gpu->ctl2.hbm.ADR_DLY);
		printf("Power Management related timings:\n");
		printf("  \t  CKSRE: %d\t", gpu->pmg.hbm.CKSRE);
		printf("  CKSRX: %d\t", gpu->pmg.hbm.CKSRX);
		printf("  CKE_PULSE: %d\t", gpu->pmg.hbm.CKE_PULSE);
		printf("  CKE: %d\t", gpu->pmg.hbm.CKE);
		printf("  SEQ_IDLE: %d\n", gpu->pmg.hbm.SEQ_IDLE);
		printf("RAS related timings:\n");
		printf("  \t  RC: %d\t", gpu->ras.RC);
		printf("  RRD: %d\t", gpu->ras.RRD);
		printf("  RCDRA: %d\t", gpu->ras.RCDRA);
		printf("  RCDR: %d\t", gpu->ras.RCDR);
		printf("  RCDWA: %d\t", gpu->ras.RCDWA);
		printf("  RCDW: %d\n", gpu->ras.RCDW);
		printf("CAS related timings:\n");
		printf("  \t  CL: %d\t", gpu->cas.hbm.CL);
		printf("  W2R: %d\t", gpu->cas.hbm.W2R);
		printf("  R2R: %d\t", gpu->cas.hbm.R2R);
		printf("  CCDL: %d\t", gpu->cas.hbm.CCDL);
		printf("  R2W: %d\t", gpu->cas.hbm.R2W);
		printf("  NOPR: %d\t", gpu->cas.hbm.NOPR);
		printf("  NOPW: %d\n", gpu->cas.hbm.NOPW);
		printf("Misc. DRAM timings:\n");
		printf("  \t  MRD: %d\t", gpu->misc.hbm.MRD);
		printf("  RRDL: %d\t", gpu->misc.hbm.RRDL);
		printf("  RFC: %d\t", gpu->misc.hbm.RFC);
		printf("  TRP: %d\t", gpu->misc.hbm.TRP);
		printf("  RP_RDA: %d\t", gpu->misc.hbm.RP_RDA);
		printf("  RP_WRA: %d\n", gpu->misc.hbm.RP_WRA);
		printf("Misc2. DRAM timings:\n");
		printf("  \t  WDATATR: %d\t", gpu->misc2.hbm.WDATATR);
		printf("  T32AW: %d\t", gpu->misc2.hbm.T32AW);
		printf("  RPAR: %d\t", gpu->misc2.hbm.RPAR);
		printf("  WPAR: %d\t", gpu->misc2.hbm.WPAR);
		printf("  FAW: %d\t", gpu->misc2.hbm.FAW);
		printf("  PA2WDATA: %d\t", gpu->misc2.hbm.PA2WDATA);
		printf("  PA2RDATA: %d\n", gpu->misc2.hbm.PA2RDATA);
		printf("Mode Register 0:\n");
		printf("  \t  DBR: %d\t", gpu->smisc1.hbm.DBR);
		printf("  DBW: %d\t", gpu->smisc1.hbm.DBW);
		printf("  TCSR: %d\t", gpu->smisc1.hbm.TCSR);
		printf("  DQR: %d\n", gpu->smisc1.hbm.DQR);
		printf("  \t  DQW: %d\t ", gpu->smisc1.hbm.DQW);
		printf("  ADD_PAR: %d\t ", gpu->smisc1.hbm.ADD_PAR);
		printf("  TM: %d\n", gpu->smisc1.hbm.TM);
		printf("Mode Register 1:\n");
		printf("  \t  WR: %d  \t", gpu->smisc1.hbm.WR);
		printf("  NDS: %d\n", gpu->smisc1.hbm.NDS);
		printf("Mode Register 2:\n");
		printf("  \t  WL: %d  \t", gpu->smisc1.hbm.WL);
		printf("  RL: %d\n", gpu->smisc1.hbm.RL);
		printf("Mode Register 3:\n");
		printf("  \t  APRAS: %d  \t", gpu->smisc1.hbm.APRAS);
		printf("  BG: %d   \t", gpu->smisc1.hbm.BG);
		printf("  BL: %d\n", gpu->smisc1.hbm.BL);
		printf("Refresh Interval:\n");
		printf("  \t  REF: %d\n", gpu->ref.REF);
		printf("Thermal Throttle Control:\n");
		printf("  \t  THRESH: %d\t", gpu->throt.THRESH);
		printf("  LEVEL: %d\t", gpu->throt.LEVEL);
		printf("  PWRDOWN: %d\t", gpu->throt.PWRDOWN);
		printf("  SHUTDOWN: %d\t", gpu->throt.SHUTDOWN);
		printf("  EN_SHUTDOWN: %d\t", gpu->throt.EN_SHUTDOWN);
		printf("  OVERSAMPLE: %d\t", gpu->throt.OVERSAMPLE);
		printf("  AVG_SAMPLE: %d\n", gpu->throt.AVG_SAMPLE);
		printf("Hammer:\n");
		printf("  \t  ENB: %d\t", gpu->ham.ENB);
		printf("  CNT: %d\t", gpu->ham.CNT);
		printf("  TRC: %d\n", gpu->ham.TRC);
	}
	else // GDDR5
	{
		MANUFACTURER man = gpu->man;
		printf((man.rx.MAN == 0x1) ? "   Samsung GDDR5" :
			(man.rx.MAN == 0x3) ? "   Elpida GDDR5" :
			(man.rx.MAN == 0x6) ? "   Hynix GDDR5" :
			(man.rx.MAN == 0xf) ? "   Micron GDDR5" : "   Unknown");
		printf("\n\nChannel 0's write command parameters:\n");
		printf("  \t  DAT_DLY: %d\t", gpu->ctl1.rx.DAT_DLY);
		printf("  DQS_DLY: %d\t", gpu->ctl1.rx.DQS_DLY);
		printf("  DQS_XTR: %d\t", gpu->ctl1.rx.DQS_XTR);
		printf("  DAT_2Y_DLY: %d\t", gpu->ctl1.rx.DAT_2Y_DLY);
		printf("  ADR_2Y_DLY: %d\t", gpu->ctl1.rx.ADR_2Y_DLY);
		printf("  CMD_2Y_DLY: %d\t", gpu->ctl1.rx.CMD_2Y_DLY);
		printf("  OEN_DLY: %d\n", gpu->ctl1.rx.OEN_DLY);
		printf("  \t  OEN_EXT: %d\t", gpu->ctl1.rx.OEN_EXT);
		printf("  OEN_SEL: %d\t", gpu->ctl1.rx.OEN_SEL);
		printf("  ODT_DLY: %d\t", gpu->ctl1.rx.ODT_DLY);
		printf("  ODT_EXT: %d\t", gpu->ctl1.rx.ODT_EXT);
		printf("  ADR_DLY: %d\t", gpu->ctl1.rx.ADR_DLY);
		printf("  CMD_DLY: %d\n", gpu->ctl1.rx.CMD_DLY);
		printf("Channel 1's write command parameters:\n");
		printf("  \t  DAT_DLY: %d\t", gpu->ctl2.rx.DAT_DLY);
		printf("  DQS_DLY: %d\t", gpu->ctl2.rx.DQS_DLY);
		printf("  DQS_XTR: %d\t", gpu->ctl2.rx.DQS_XTR);
		printf("  DAT_2Y_DLY: %d\t", gpu->ctl2.rx.DAT_2Y_DLY);
		printf("  ADR_2Y_DLY: %d\t", gpu->ctl2.rx.ADR_2Y_DLY);
		printf("  CMD_2Y_DLY: %d\t", gpu->ctl2.rx.CMD_2Y_DLY);
		printf("  OEN_DLY: %d\n", gpu->ctl2.rx.OEN_DLY);
		printf("  \t  OEN_EXT: %d\t", gpu->ctl2.rx.OEN_EXT);
		printf("  OEN_SEL: %d\t", gpu->ctl2.rx.OEN_SEL);
		printf("  ODT_DLY: %d\t", gpu->ctl2.rx.ODT_DLY);
		printf("  ODT_EXT: %d\t", gpu->ctl2.rx.ODT_EXT);
		printf("  ADR_DLY: %d\t", gpu->ctl2.rx.ADR_DLY);
		printf("  CMD_DLY: %d\n", gpu->ctl2.rx.CMD_DLY);
		printf("Power Mangement related timings:\n");
		printf("  \t  CKSRE: %d\t", gpu->pmg.rx.CKSRE);
		printf("  CKSRX: %d\t", gpu->pmg.rx.CKSRX);
		printf("  CKE_PULSE: %d\t", gpu->pmg.rx.CKE_PULSE);
		printf("  CKE: %d\t", gpu->pmg.rx.CKE);
		printf("  SEQ_IDLE: %d\n", gpu->pmg.rx.SEQ_IDLE);
		printf("RAS related timings:\n");
		printf("  \t  RC: %d\t", gpu->ras.RC);
		printf("  RRD: %d\t", gpu->ras.RRD);
		printf("  RCDRA: %d\t", gpu->ras.RCDRA);
		printf("  RCDR: %d\t", gpu->ras.RCDR);
		printf("  RCDWA: %d\t", gpu->ras.RCDWA);
		printf("  RCDW: %d\n", gpu->ras.RCDW);
		printf("CAS related timings:\n");
		printf("  \t  CL: %d\t", gpu->cas.rx.CL);
		printf("  W2R: %d\t", gpu->cas.rx.W2R);
		printf("  R2R: %d\t", gpu->cas.rx.R2R);
		printf("  CCDL: %d\t", gpu->cas.rx.CCDL);
		printf("  R2W: %d\t", gpu->cas.rx.R2W);
		printf("  NOPR: %d\t", gpu->cas.rx.NOPR);
		printf("  NOPW: %d\n", gpu->cas.rx.NOPW);
		printf("Misc. DRAM timings:\n");
		if (IsR9(gpu->dev))
		{
			printf("  \t  RFC: %d\t", gpu->misc.r9.RFC);
			printf("  TRP: %d\t", gpu->misc.r9.TRP);
			printf("  RP_RDA: %d\t", gpu->misc.r9.RP_RDA);
			printf("  RP_WRA: %d\n", gpu->misc.r9.RP_WRA);
		}
		else
		{
			printf("  \t  RFC: %d\t", gpu->misc.rx.RFC);
			printf("  TRP: %d\t", gpu->misc.rx.TRP);
			printf("  RP_RDA: %d\t", gpu->misc.rx.RP_RDA);
			printf("  RP_WRA: %d\n", gpu->misc.rx.RP_WRA);
		}
		printf("Misc2. DRAM timings:\n");
		printf("  \t  WDATATR: %d\t", gpu->misc2.rx.WDATATR);
		printf("  T32AW: %d\t", gpu->misc2.rx.T32AW);
		printf("  WEDC: %d\t", gpu->misc2.rx.WEDC);
		printf("  REDC: %d\t", gpu->misc2.rx.REDC);
		printf("  FAW: %d\t", gpu->misc2.rx.FAW);
		printf("  PA2WDATA: %d\t", gpu->misc2.rx.PA2WDATA);
		printf("  PA2RDATA: %d\n", gpu->misc2.rx.PA2RDATA);
		printf("Mode Register 0:\n");
		printf("  \t  WL: %d  \t", gpu->smisc1.rx.WL);
		printf("  CL: %d  \t", gpu->smisc1.rx.CL);
		printf("  TM: %d  \t", gpu->smisc1.rx.TM);
		printf("  WR: %d\n", gpu->smisc1.rx.WR);
		printf("  \t  BA0: %d\t ", gpu->smisc1.rx.BA0);
		printf("  BA1: %d\t ", gpu->smisc1.rx.BA1);
		printf("  BA2: %d\t ", gpu->smisc1.rx.BA2);
		printf("  BA3: %d\n", gpu->smisc1.rx.BA3);
		printf("Mode Register 1:\n");
		printf("  \t  DS: %d  \t", gpu->smisc1.rx.DS);
		printf("  DT: %d  \t", gpu->smisc1.rx.DT);
		printf("  ADR: %d\t ", gpu->smisc1.rx.ADR);
		printf("  CAL: %d\t ", gpu->smisc1.rx.CAL);
		printf("  PLL: %d\n ", gpu->smisc1.rx.PLL);
		printf("  \t  RDBI: %d\t", gpu->smisc1.rx.RDBI);
		printf("  WDBI: %d\t", gpu->smisc1.rx.WDBI);
		printf("  ABI: %d\t", gpu->smisc1.rx.ABI);
		printf("  RESET: %d\n", gpu->smisc1.rx.RESET);
		printf("  \t  BA0: %d\t ", gpu->smisc1.rx.BA_0);
		printf("  BA1: %d\t ", gpu->smisc1.rx.BA_1);
		printf("  BA2: %d\t ", gpu->smisc1.rx.BA_2);
		printf("  BA3: %d\n", gpu->smisc1.rx.BA_3);
		printf("Mode Register 2:\n");
		printf("  \t  OCD_DWN: %d\t", gpu->smisc2.OCD_DWN);
		printf("  OCD_UP: %d\t", gpu->smisc2.OCD_UP);
		printf("  WCK: %d\t ", gpu->smisc2.WCK);
		printf("  ADR: %d\n ", gpu->smisc2.ADR);
		printf("  \t  BA0: %d\t ", gpu->smisc2.BA0);
		printf("  BA1: %d\t ", gpu->smisc2.BA1);
		printf("  BA2: %d\t ", gpu->smisc2.BA2);
		printf("  BA3: %d\n", gpu->smisc2.BA3);
		printf("Mode Register 3:\n");
		printf("  \t  SR: %d  \t", gpu->smisc2.SR);
		printf("  WCK01: %d\t", gpu->smisc2.WCK01);
		printf("  WCK23: %d\t", gpu->smisc2.WCK23);
		printf("  WCK2CK: %d\t", gpu->smisc2.WCK2CK);
		printf("  RDQS: %d\t", gpu->smisc2.RDQS);
		printf("  INFO: %d\t", gpu->smisc2.INFO);
		printf("  WCK2: %d\n", gpu->smisc2.WCK2);
		printf("  \t  BA0: %d\t ", gpu->smisc2.BA_0);
		printf("  BA1: %d\t ", gpu->smisc2.BA_1);
		printf("  BA2: %d\t ", gpu->smisc2.BA_2);
		printf("  BA3: %d\n", gpu->smisc2.BA_3);
		printf("Mode Register 4:\n");
		printf("  \t  EDCHP: %d\t", gpu->smisc3.EDCHP);
		printf("  CRCWL: %d\t", gpu->smisc3.CRCWL);
		printf("  CRCRL: %d\t", gpu->smisc3.CRCRL);
		printf("  RDCRC: %d\t", gpu->smisc3.RDCRC);
		printf("  WRCRC: %d\t", gpu->smisc3.WRCRC);
		printf("  EDC: %d\n ", gpu->smisc3.EDC);
		printf("  \t  BA0: %d\t ", gpu->smisc3.BA0);
		printf("  BA1: %d\t ", gpu->smisc3.BA1);
		printf("  BA2: %d\t ", gpu->smisc3.BA2);
		printf("  BA3: %d\n", gpu->smisc3.BA3);
		printf("Mode Register 5:\n");
		printf("  \t  LP1: %d\t ", gpu->smisc3.LP1);
		printf("  LP1: %d\t ", gpu->smisc3.LP1);
		printf("  LP1: %d\t ", gpu->smisc3.LP1);
		printf("  PLL: %d\t ", gpu->smisc3.PLL);
		printf("  RAS: %d\n ", gpu->smisc3.RAS);
		printf("  \t  BA0: %d\t ", gpu->smisc3.BA_0);
		printf("  BA1: %d\t ", gpu->smisc3.BA_1);
		printf("  BA2: %d\t ", gpu->smisc3.BA_2);
		printf("  BA3: %d\n", gpu->smisc3.BA_3);
		printf("Mode Register 6:\n");
		printf("  \t  WCK: %d\t ", gpu->smisc4.WCK);
		printf("  VREFD_M: %d\t", gpu->smisc4.VREFD_M);
		printf("  A_VREFD: %d\t", gpu->smisc4.A_VREFD);
		printf("  VREFD: %d\t", gpu->smisc4.VREFD);
		printf("  VREFD_O: %d\t", gpu->smisc4.VREFD_O);
		printf("  VREFD_0_2: %d\n", gpu->smisc4.VREFD_0_2);
		printf("  \t  BA0: %d\t ", gpu->smisc4.BA0);
		printf("  BA1: %d\t ", gpu->smisc4.BA1);
		printf("  BA2: %d\t ", gpu->smisc4.BA2);
		printf("  BA3: %d\n", gpu->smisc4.BA3);
		printf("Mode Register 7:\n");
		printf("  \t  PLL_STD: %d\t", gpu->smisc4.PLL_STD);
		printf("  PLL_FL: %d\t", gpu->smisc4.PLL_FL);
		printf("  PLL_DEL: %d\t", gpu->smisc4.PLL_DEL);
		printf("  LF_MOD: %d\t", gpu->smisc4.LF_MOD);
		printf("  AUTO: %d\t", gpu->smisc4.AUTO);
		printf("  DQ: %d\n  ", gpu->smisc4.DQ);
		printf("  \t  TEMP: %d\t", gpu->smisc4.TEMP);
		printf("  HALF: %d\t", gpu->smisc4.HALF);
		printf("  VDD_R: %d\t", gpu->smisc4.VDD_R);
		printf("  RFU: %d\n ", gpu->smisc4.RFU);
		printf("  \t  BA0: %d\t ", gpu->smisc4.BA_0);
		printf("  BA1: %d\t ", gpu->smisc4.BA_1);
		printf("  BA2: %d\t ", gpu->smisc4.BA_2);
		printf("  BA3: %d\n", gpu->smisc4.BA_3);
		printf("Mode Register 15:\n");
		printf("  \t  MRE0: %d\t", gpu->smisc7.MRE0);
		printf("  MRE1: %d\t", gpu->smisc7.MRE1);
		printf("  ADT: %d\t ", gpu->smisc7.ADT);
		printf("  RFU: %d\n ", gpu->smisc7.RFU);
		printf("  \t  BA0: %d\t ", gpu->smisc7.BA0);
		printf("  BA1: %d\t ", gpu->smisc7.BA1);
		printf("  BA2: %d\t ", gpu->smisc7.BA2);
		printf("  BA3: %d\n", gpu->smisc7.BA3);
		printf("Mode Register 8:\n");
		printf("  \t  CLEHF: %d\t", gpu->smisc8.CLEHF);
		printf("  WREHF: %d\t", gpu->smisc8.WREHF);
		printf("  RFU: %d\n ", gpu->smisc8.RFU);
		printf("  \t  BA0: %d\t ", gpu->smisc8.BA0);
		printf("  BA1: %d\t ", gpu->smisc8.BA1);
		printf("  BA2: %d\t ", gpu->smisc8.BA2);
		printf("  BA3: %d\n", gpu->smisc8.BA3);
		printf("DRAM Specific:\n");
		printf("  \t  RASMACTWR: %d\t", gpu->dram1.RASMACTWR);
		printf("  RASMACTRD: %d\t", gpu->dram1.RASMACTRD);
		printf("  ACTWR: %d\t", gpu->dram1.ACTWR);
		printf("  ACTRD: %d\n", gpu->dram1.ACTRD);
		printf("DRAM2 Specific:\n");
		printf("  \t  RAS2RAS: %d\t", gpu->dram2.RAS2RAS);
		printf("  RP: %d\t", gpu->dram2.RP);
		printf("  WRPLUSRP: %d\t", gpu->dram2.WRPLUSRP);
		printf("  BUS_TURN: %d\n", gpu->dram2.BUS_TURN);
		printf("Refresh Interval:\n");
		printf("  \t  REF: %d\n", gpu->ref.REF);
		printf("Training timings:\n");
		printf("  \t  TWT2RT: %d\t", gpu->train.TWT2RT);
		printf("  TARF2T: %d\t", gpu->train.TARF2T);
		printf("  TT2ROW: %d\t", gpu->train.TT2ROW);
		printf("  TLD2LD: %d\n\n", gpu->train.TLD2LD);
	}
}

static void PrintCurrentValuesJson(GPU * gpu, int index)
{
	if (DetermineMemoryType(gpu->dev) != HBM2)
	{
		fprintf(stderr, "JSON output is currently supported for HBM2 devices only.\n");
		return;
	}

	HBM2_TIMINGS current = gpu->hbm2;
	MANUFACTURER man = gpu->man;
	const char* vendor =
		(man.hbm.MAN == 0x63) ? "Hynix HBM2" :
		(man.hbm.MAN == 0x61) ? "Samsung HBM2" : "Unknown";

	printf("{\"gpu\":%d,\"bdf\":\"%04x:%02x:%02x.%d\","
		"\"memoryType\":\"HBM2\",\"memoryVendor\":\"%s\","
		"\"memoryStateRaw\":%u,\"timings\":{",
		index, gpu->dev->domain, gpu->dev->bus, gpu->dev->dev, gpu->dev->func,
		vendor, current.frequency);
	printf("\"cl\":%u,\"ras\":%u,\"rcdrd\":%u,\"rcdwr\":%u,",
		current.CL, current.RAS, current.RCDRD, current.RCDWR);
	printf("\"rc\":%u,\"rcpb\":%u,\"rp\":%u,\"rppb\":%u,",
		current.RCAb, current.RCPb, current.RPAb, current.RPPb);
	printf("\"rrds\":%u,\"rrdl\":%u,\"rtp\":%u,\"faw\":%u,",
		current.RRDS, current.RRDL, current.RTP, current.FAW);
	printf("\"cwl\":%u,\"wtrs\":%u,\"wtrl\":%u,\"wr\":%u,",
		current.CWL, current.WTRS, current.WTRL, current.WR);
	printf("\"rrefd\":%u,\"rdrddd\":%u,\"rdrdsd\":%u,"
		"\"rdrdsc\":%u,\"rdrdscl\":%u,",
		current.RREFD, current.RDRDDD, current.RDRDSD,
		current.RDRDSC, current.RDRDSCL);
	printf("\"wrwrdd\":%u,\"wrwrsd\":%u,\"wrwrsc\":%u,"
		"\"wrwrscl\":%u,\"wrrd\":%u,\"rdwr\":%u,",
		current.WRWRDD, current.WRWRSD, current.WRWRSC,
		current.WRWRSCL, current.WRRD, current.RDWR);
	printf("\"ref\":%u,\"mrd\":%u,\"mod\":%u,\"xs\":%u,"
		"\"xsmrs\":%u,\"pd\":%u,\"cksre\":%u,\"cksrx\":%u,",
		current.REF, current.MRD, current.MOD, current.XS,
		current.XSMRS, current.PD, current.CKSRE, current.CKSRX);
	printf("\"rfcpb\":%u,\"stag\":%u,\"xp\":%u,\"cpded\":%u,"
		"\"cke\":%u,\"rddata\":%u,\"wrlat\":%u,\"rdlat\":%u,"
		"\"wrdata\":%u,\"ckestag\":%u,\"rfc\":%u}}\n",
		current.RFCPB, current.STAG, current.XP, current.CPDED,
		current.CKE, current.RDDATA, current.WRLAT, current.RDLAT,
		current.WRDATA, current.CKESTAG, current.RFC);
}

void ReadMMIO(GPU * gpu);

int main(int argc, const char* argv[])
{
	GPU gpus[64] = {};
	bool jsonOutput = false;
	for (int i = 1; i < argc; i++)
	{
		if (!strcasecmp("--json", argv[i])) jsonOutput = true;
	}

	if ((argc < 2) || (0 == strcasecmp("--help", argv[1])) || (0 == strcasecmp("--h", argv[1])))
	{
		printf(" AMD Memory Tweak\n"
			" Read and modify memory timings on the fly\n"
			" By Eliovp & A.Solodovnikov\n\n"
			" Global command line options:\n"
			" --help|--h\tShow this output\n"
			" --version|--v\tShow version info\n"
			" --gpu|--i [comma-separated gpu indices]\tSelected device(s)\n"
			" --current|--c\tList current timing values\n"
			" --json\tPrint --current as one JSON object per GPU\n\n"
			" Command line options: (HBM2)\n"
			" --CL|--cl [value]\n"
			" --RAS|--ras [value]\n"
			" --RCDRD|--rcdrd [value]\n"
			" --RCDWR|--rcdwr [value]\n"
			" --RC|--rc [value]\n"
			" --RP|--rp [value]\n"
			" --RRDS|--rrds [value]\n"
			" --RRDL|--rrdl [value]\n"
			" --RTP|--rtp [value]\n"
			" --FAW|--faw [value]\n"
			" --CWL|--cwl [value]\n"
			" --WTRS|--wtrs [value]\n"
			" --WTRL|--wtrl [value]\n"
			" --WR|--wr [value]\n"
			" --RREFD|--rrefd [value]\n"
			" --RDRDDD|--rdrddd [value]\n"
			" --RDRDSD|--rdrdsd [value]\n"
			" --RDRDSC|--rdrdsc [value]\n"
			" --RDRDSCL|--rdrdscl [value]\n"
			" --WRWRDD|--wrwrdd [value]\n"
			" --WRWRSD|--wrwrsd [value]\n"
			" --WRWRSC|--wrwrsc [value]\n"
			" --WRWRSCL|--wrwrscl [value]\n"
			" --WRRD|--wrrd [value]\n"
			" --RDWR|--rdwr [value]\n"
			" --REF|--ref [value]\n"
			" --MRD|--mrd [value]\n"
			" --MOD|--mod [value]\n"
			" --XS|--xs [value]\n"
			" --XSMRS|--xsmrs [value]\n"
			" --PD|--pd [value]\n"
			" --CKSRE|--cksre [value]\n"
			" --CKSRX|--cksrx [value]\n"
			" --RFCPB|--rfcpb [value]\n"
			" --STAG|--stag [value]\n"
			" --XP|--xp [value]\n"
			" --CPDED|--cpded [value]\n"
			" --CKE|--cke [value]\n"
			" --RDDATA|--rddata [value]\n"
			" --WRLAT|--wrlat [value]\n"
			" --RDLAT|--rdlat [value]\n"
			" --WRDATA|--wrdata [value]\n"
			" --CKESTAG|--ckestag [value]\n"
			" --RFC|--rfc [value]\n\n"
			" Command line options: (HBM)\n"
			" --DAT_DLY0|1|2|3 | --dat_dly0|1|2|3 [value]\n"
			" --DQS_DLY0|1|2|3 | --dqs_dly0|1|2|3 [value]\n"
			" --DQS_XTR0|1|2|3 | --dqs_xtr0|1|2|3 [value]\n"
			" --OEN_DLY0|1|2|3 | --oen_dly0|1|2|3 [value]\n"
			" --OEN_EXT0|1|2|3 | --oen_ext0|1|2|3 [value]\n"
			" --OEN_SEL0|1|2|3 | --oen_sel0|1|2|3 [value]\n"
			" --CMD_DLY0|1|2|3 | --cmd_dly0|1|2|3 [value]\n"
			" --ADR_DLY0|1|2|3 | --adr_dly0|1|2|3 [value]\n"
			" --CKSRE|--cksre [value]\n"
			" --CKSRX|--cksrx [value]\n"
			" --CKE_PULSE|--cke_pulse [value]\n"
			" --CKE|--cke [value]\n"
			" --SEQ_IDLE|--seq_idle [value]\n"
			" --CL|--cl [value]\n"
			" --W2R|--w2r [value]\n"
			" --R2R|--r2r [value]\n"
			" --CCDL|--ccdl [value]\n"
			" --R2W|--r2w [value]\n"
			" --NOPR|--nopr [value]\n"
			" --NOPW|--nopw [value]\n"
			" --RCDW|--rcdw [value]\n"
			" --RCDWA|--rcdwa [value]\n"
			" --RCDR|--rcdr [value]\n"
			" --RCDRA|--rcdra [value]\n"
			" --RRD|--rrd [value]\n"
			" --RC|--rc [value]\n"
			" --MRD|--mrd [value]\n"
			" --RRDL|--rrdl [value]\n"
			" --RFC|--rfc [value]\n"
			" --TRP|--trp [value]\n"
			" --RP_WRA|--rp_wra [value]\n"
			" --RP_RDA|--rp_rda [value]\n"
			" --WDATATR|--wdatatr [value]\n"
			" --T32AW|--t32aw [value]\n"
			" --CRCWL|--crcwl [value]\n"
			" --CRCRL|--crcrl [value]\n"
			" --FAW|--faw [value]\n"
			" --PA2WDATA|--pa2wdata [value]\n"
			" --PA2RDATA|--pa2rdata [value]\n"
			" --DBR|--dbr [value]\n"
			" --DBW|--dbw [value]\n"
			" --TCSR|--tcsr [value]\n"
			" --DQR|--dqr [value]\n"
			" --DQW|--dqw [value]\n"
			" --ADD_PAR|--add_par [value]\n"
			" --TM|--tm [value]\n"
			" --WR|--wr [value]\n"
			" --NDS|--nds [value]\n"
			" --WL|--wl [value]\n"
			" --RL|--rl [value]\n"
			" --APRAS|--apras [value]\n"
			" --BG|--bg [value]\n"
			" --BL|--bl [value]\n"
			" --REF|--ref [value]\n"
			" --ENB|--enb [value]\n"
			" --CNT|--cnt [value]\n"
			" --TRC|--trc [value]\n"
			" --THRESH|--thresh [value]\n"
			" --LEVEL|--level [value]\n"
			" --PWRDOWN|--pwrdown [value]\n"
			" --SHUTDOWN|--shutdown [value]\n"
			" --EN_SHUTDOWN|--en_shutdown [value]\n"
			" --OVERSAMPLE|--oversample [value]\n"
			" --AVG_SAMPLE|--avg_sample [value]\n\n"
			" Command line options: (GDDR5)\n"
			" --DAT_DLY0|1 | --dat_dly0|1 [value]\n"
			" --DQS_DLY0|1 | --dqs_dly0|1 [value]\n"
			" --DQS_XTR0|1 | --dqs_xtr0|1 [value]\n"
			" --DAT_2Y_DLY0|1 | --dat_2y_dly0|1 [value]\n"
			" --ADR_2Y_DLY0|1 | --adr_2y_dly0|1 [value]\n"
			" --CMD_2Y_DLY0|1 | --cmd_2y_dly0|1 [value]\n"
			" --OEN_DLY0|1 | --oen_dly0|1 [value]\n"
			" --OEN_EXT0|1 | --oen_ext0|1 [value]\n"
			" --OEN_SEL0|1 | --oen_sel0|1 [value]\n"
			" --ODT_DLY0|1 | --odt_dly0|1 [value]\n"
			" --ODT_EXT0|1 | --odt_ext0|1 [value]\n"
			" --ADR_DLY0|1 | --adr_dly0|1 [value]\n"
			" --CMD_DLY0|1 | --cmd_dly0|1 [value]\n"
			" --CKSRE|--cksre [value]\n"
			" --CKSRX|--cksrx [value]\n"
			" --CKE_PULSE|--cke_pulse [value]\n"
			" --CKE|--cke [value]\n"
			" --SEQ_IDLE|--seq_idle [value]\n"
			" --CL|--cl [value]\n"
			" --W2R|--w2r [value]\n"
			" --R2R|--r2r [value]\n"
			" --CCDL|--ccdl [value]\n"
			" --R2W|--r2w [value]\n"
			" --NOPR|--nopr [value]\n"
			" --NOPW|--nopw [value]\n"
			" --RCDW|--rcdw [value]\n"
			" --RCDWA|--rcdwa [value]\n"
			" --RCDR|--rcdr [value]\n"
			" --RCDRA|--rcdra [value]\n"
			" --RRD|--rrd [value]\n"
			" --RC|--rc [value]\n"
			" --RFC|--rfc [value]\n"
			" --TRP|--trp [value]\n"
			" --RP_WRA|--rp_wra [value]\n"
			" --RP_RDA|--rp_rda [value]\n"
			" --WDATATR|--wdatatr [value]\n"
			" --T32AW|--t32aw [value]\n"
			" --CRCWL|--crcwl [value]\n"
			" --CRCRL|--crcrl [value]\n"
			" --FAW|--faw [value]\n"
			" --PA2WDATA|--pa2wdata [value]\n"
			" --PA2RDATA|--pa2rdata [value]\n"
			" --WL|--wl [value]\n"
			" --MR0_CL|--mr0_cl [value]\n"
			" --TM|--tm [value]\n"
			" --WR|--wr [value]\n"
			" --DS|--ds [value]\n"
			" --DT|--dt [value]\n"
			" --ADR|--adr [value]\n"
			" --CAL|--cal [value]\n"
			" --PLL|--pll [value]\n"
			" --RDBI|--rdbi [value]\n"
			" --WDBI|--wdbi [value]\n"
			" --ABI|--abi [value]\n"
			" --RESET|--reset [value]\n"
			" --SR|--sr [value]\n"
			" --WCK01|--wck01 [value]\n"
			" --WCK23|--wck23 [value]\n"
			" --WCK2CK|--wck2ck [value]\n"
			" --RDQS|--rdqs [value]\n"
			" --INFO|--info [value]\n"
			" --WCK2|--wck2 [value]\n"
			" --BG|--bg [value]\n"
			" --EDCHP|--edchp [value]\n"
			" --CRCWL|--crcwl [value]\n"
			" --CRCRL|--crcrl [value]\n"
			" --RDCRC|--rdcrc [value]\n"
			" --WRCRC|--wrcrc [value]\n"
			" --EDC|--edc [value]\n"
			" --RAS|--ras [value]\n"
			" --CLEHF|--clehf [value]\n"
			" --WREHF|--wrehf [value]\n"
			" --ACTRD|--actrd [value]\n"
			" --ACTWR|--actwr [value]\n"
			" --RASMACTRD|--rasmactrd [value]\n"
			" --RASMACWTR|--rasmacwtr [value]\n"
			" --RAS2RAS|--ras2ras [value]\n"
			" --RP|--rp [value]\n"
			" --WRPLUSRP|--wrplusrp [value]\n"
			" --BUS_TURN|--bus_turn [value]\n"
			" --REF|--ref [value]\n"
			" --TWT2RT|--twt2rt [value]\n"
			" --TARF2T|--tarf2t [value]\n"
			" --TT2ROW|--tt2row [value]\n"
			" --TLD2LD|--tld2ld [value]\n\n"
			" HBM2 Example usage: ./amdmemtool --i 0,3,5 --faw 12 --RFC 208\n"
			" HBM Example usage: ./amdmemtool --i 6 --ref 13\n"
			" GDDR5 Example usage: ./amdmemtool --i 1,2,4 --RFC 43 --ras2ras 176\n\n"
			" Make sure to run the program first with parameter --current to see what the current values are.\n"
			" Current values may change based on state of the GPU,\n"
			" in other words, make sure the GPU is under load when running --current\n"
			" HBM2 Based GPU's do not need to be under load to apply timing changes.\n"
			" Hint: Certain timings such as CL (Cas Latency) are stability timings, lowering these will lower stability.\n");
		return 0;
	}

	if (!strcasecmp("--version", argv[1]) || !strcasecmp("--v", argv[1]))
	{
		printf(VERSION);
		return EXIT_SUCCESS;
	}

	struct pci_access* pci = pci_alloc();
	pci_init(pci);
	pci_scan_bus(pci);
	int gpuCount = 0;
	for (struct pci_dev* dev = pci->devices; dev; dev = dev->next)
	{
		pci_fill_info(dev, PCI_FILL_IDENT | PCI_FILL_BASES | PCI_FILL_ROM_BASE | PCI_FILL_SIZES | PCI_FILL_CLASS);
		if (IsAmdDisplayDevice(dev))
		{
			gpus[gpuCount++].dev = dev;
		}
	}

	if (gpuCount == 0)
	{
		printf("No AMD display devices have been found!\n");
		return 0;
	}

	qsort(gpus, gpuCount, sizeof(GPU), gpu_compare);

	//printf("Detected GPU's\n");
	for (int i = 0; i < gpuCount; i++)
	{
		GPU* gpu = &gpus[i];

		char buffer[1024];
		//char *name = pci_lookup_name(pci, buffer, sizeof(buffer), PCI_LOOKUP_DEVICE, gpu->dev->vendor_id, gpu->dev->device_id);
		//printf(" (%s)\n", name);

		snprintf(buffer, sizeof(buffer) - 1, "%04x:%02x:%02x.%d", gpu->dev->domain, gpu->dev->bus, gpu->dev->dev, gpu->dev->func);
		int instance = pci_find_instance(buffer);
		if (instance == -1)
		{
			fprintf(stderr, "Cannot find DRI instance for pci:%s\n", buffer);
			return 1;
		}

		snprintf(buffer, sizeof(buffer) - 1, "/sys/kernel/debug/dri/%d/amdgpu_regs", instance);
		gpu->mmio = open(buffer, O_RDWR);
		if (gpu->mmio == -1)
		{
			gpu->mmio = open(buffer, O_RDONLY);
		}
		if (gpu->mmio == -1)
		{
			fprintf(stderr, "Failed to open %s\n", buffer);
			return 1;
		}

		switch (DetermineMemoryType(gpu->dev))
		{
		case HBM2:
			for (int j = 0; j < sizeof(HBM2_TIMINGS) / 4; j++)
			{
				*((u32*)& gpu->hbm2 + j) = ReadMMIODword(AMD_TIMING_REGS_BASE_1 + j * sizeof(u32), gpu);
			}
			gpu->man.value = ReadMMIODword(MANUFACTURER_ID_HBM2, gpu);
			break;
		case GDDR5:
			gpu->ctl1.value = ReadMMIODword(MC_SEQ_WR_CTL_D0, gpu);
			gpu->ctl2.value = ReadMMIODword(MC_SEQ_WR_CTL_D1, gpu);
			gpu->pmg.value = ReadMMIODword(MC_SEQ_PMG_TIMING, gpu);
			gpu->ras.value = ReadMMIODword(MC_SEQ_RAS_TIMING, gpu);
			gpu->cas.value = ReadMMIODword(MC_SEQ_CAS_TIMING, gpu);
			gpu->misc.value = ReadMMIODword(MC_SEQ_MISC_TIMING, gpu);
			gpu->misc2.value = ReadMMIODword(MC_SEQ_MISC_TIMING2, gpu);
			gpu->smisc1.value = ReadMMIODword(MC_SEC_MISC1, gpu);
			gpu->smisc2.value = ReadMMIODword(MC_SEC_MISC2, gpu);
			gpu->smisc3.value = ReadMMIODword(MC_SEC_MISC3, gpu);
			gpu->smisc4.value = ReadMMIODword(MC_SEC_MISC4, gpu);
			gpu->smisc7.value = ReadMMIODword(MC_SEC_MISC7, gpu);
			gpu->smisc8.value = ReadMMIODword(MC_SEC_MISC8, gpu);
			gpu->dram1.value = ReadMMIODword(MC_ARB_DRAM_TIMING, gpu);
			gpu->dram2.value = ReadMMIODword(MC_ARB_DRAM_TIMING2, gpu);
			gpu->ref.value = ReadMMIODword(MC_ARB_RFSH_RATE, gpu);
			gpu->train.value = ReadMMIODword(MC_SEQ_TRAINING, gpu);
			gpu->man.value = ReadMMIODword(MANUFACTURER_ID, gpu);
			break;
		case HBM:
			gpu->ctl1.value = ReadMMIODword(MC_SEQ_WR_CTL_D0_HBM, gpu);
			gpu->ctl2.value = ReadMMIODword(MC_SEQ_WR_CTL_D1_HBM, gpu);
			gpu->ctl3.value = ReadMMIODword(MC_SEQ_WR_CTL_D2_HBM, gpu);
			gpu->ctl4.value = ReadMMIODword(MC_SEQ_WR_CTL_D3_HBM, gpu);
			gpu->pmg.value = ReadMMIODword(MC_SEQ_PMG_TIMING_HBM, gpu);
			gpu->ras.value = ReadMMIODword(MC_SEQ_RAS_TIMING_HBM, gpu);
			gpu->cas.value = ReadMMIODword(MC_SEQ_CAS_TIMING_HBM, gpu);
			gpu->misc.value = ReadMMIODword(MC_SEQ_MISC_TIMING_HBM, gpu);
			gpu->misc2.value = ReadMMIODword(MC_SEQ_MISC_TIMING2_HBM, gpu);
			gpu->smisc1.value = ReadMMIODword(MC_SEC_MISC1_HBM, gpu);
			gpu->ref.value = ReadMMIODword(MC_ARB_RFSH_RATE, gpu);
			gpu->ham.value = ReadMMIODword(MC_SEQ_ROW_HAMMER, gpu);
			gpu->throt.value = ReadMMIODword(MC_THERMAL_THROTTLE, gpu);
			gpu->man.value = ReadMMIODword(MANUFACTURER_ID_HBM, gpu);
			break;
		}
	}

	// Scan some regs, you never know, you might find something useful ;-)
	if (!strcasecmp("--scan", argv[1]))
	{
		if ((argc < 4) || memcmp(argv[2], "0x", 2) || memcmp(argv[3], "0x", 2))
		{
			printf("--scan requires a range of addresses in hex format (for example 0x9A0290 0x9A02C4).\n");
			return EXIT_FAILURE;
		}
		u32 low = strtoul(argv[2] + 2, 0, 16);
		if ((errno == EINVAL) || (errno == ERANGE))
		{
			printf("Failed to parse %s as a hex number\n", argv[2]);
			return EXIT_FAILURE;
		}
		u32 high = strtoul(argv[3] + 2, 0, 16);
		if ((errno == EINVAL) || (errno == ERANGE))
		{
			printf("Failed to parse %s as a hex number\n", argv[3]);
			return EXIT_FAILURE;
		}

		for (int index = 0; index < gpuCount; index++)
		{
			GPU* gpu = &gpus[index];
			char buffer[1024];
			char* name = pci_lookup_name(pci, buffer, sizeof(buffer), PCI_LOOKUP_DEVICE, gpu->dev->vendor_id, gpu->dev->device_id);
			if (gpu->dev && IsRelevantDeviceID(gpu->dev))
			{
				printf("Scanning GPU %d\n", index);
				for (u32 address = low; address <= high; address += sizeof(u32))
				{
					u32 value = ReadMMIODword(address, gpu);
					printf("0x%X: %08X\n", address, value);
					usleep(50);
				}
			}
		}
		return EXIT_SUCCESS;
	}

	// Parses the command line arguments, and accumulates the changes.
	for (int index = 0; index < gpuCount; index++)
	{
		GPU* gpu = &gpus[index];
		char buffer[1024];
		char* name = pci_lookup_name(pci, buffer, sizeof(buffer), PCI_LOOKUP_DEVICE, gpu->dev->vendor_id, gpu->dev->device_id);
		if (gpu->dev && IsRelevantDeviceID(gpu->dev))
		{
			u64 affectedGPUs = 0xFFFFFFFFFFFFFFFF; // apply to all GPUs by default
			for (int i = 1; i < argc; i++)
			{
				if (!strcasecmp("--gpu", argv[i]) || !strcasecmp("--i", argv[i]))
				{
					if (i == (argc - 1))
					{
						std::cout << "Argument \"" << argv[i] << "\" requires a parameter.\n";
						return 1;
					}
					i++;
					affectedGPUs = ParseIndicesArg(argv[i]);
				}
				else if (!strcasecmp("--json", argv[i]))
				{
					continue;
				}
				else if (!strcasecmp("--current", argv[i]) || !strcasecmp("--c", argv[i]))
				{
					if (affectedGPUs & ((u64)1 << index))
					{
						if (jsonOutput)
						{
							PrintCurrentValuesJson(gpu, index);
						}
						else
						{
							std::cout << "GPU " << index << ": ";
							printf(" %s\t", name);
							PrintCurrentValues(gpu);
						}
					}
				}
				else if (affectedGPUs & ((u64)1 << index))
				{
					u32 value = 0;
					if (DetermineMemoryType(gpu->dev) == HBM2)
					{
						if (ParseNumericArg(argc, argv, i, "--CL", value))
						{
							gpu->hbm2.CL = value;
							gpu->modify[0] = true;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CL");
						}
						else if (ParseNumericArg(argc, argv, i, "--RAS", value))
						{
							gpu->hbm2.RAS = value;
							gpu->modify[0] = true;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RAS");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDRD", value))
						{
							gpu->hbm2.RCDRD = value;
							gpu->modify[0] = true;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDWR", value))
						{
							gpu->hbm2.RCDWR = value;
							gpu->modify[0] = true;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDWR");
						}
						else if (ParseNumericArg(argc, argv, i, "--RC", value))
						{
							gpu->hbm2.RCAb = value;
							gpu->hbm2.RCPb = value;
							gpu->modify[0] = true;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RC");
						}
						else if (ParseNumericArg(argc, argv, i, "--RP", value))
						{
							gpu->hbm2.RPAb = value;
							gpu->hbm2.RPPb = value;
							gpu->modify[0] = true;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RP");
						}
						else if (ParseNumericArg(argc, argv, i, "--RRDS", value))
						{
							gpu->hbm2.RRDS = value;
							gpu->modify[0] = true;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RRDL", value))
						{
							gpu->hbm2.RRDL = value;
							gpu->modify[0] = true;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RTP", value))
						{
							gpu->hbm2.RTP = value;
							gpu->modify[0] = true;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RTP");
						}
						else if (ParseNumericArg(argc, argv, i, "--FAW", value))
						{
							gpu->hbm2.FAW = value;
							gpu->modify[0] = true;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "FAW");
						}
						else if (ParseNumericArg(argc, argv, i, "--CWL", value))
						{
							gpu->hbm2.CWL = value;
							gpu->modify[0] = true;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CWL");
						}
						else if (ParseNumericArg(argc, argv, i, "--WTRS", value))
						{
							gpu->hbm2.WTRS = value;
							gpu->modify[0] = true;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WTRS");
						}
						else if (ParseNumericArg(argc, argv, i, "--WTRL", value))
						{
							gpu->hbm2.WTRL = value;
							gpu->modify[0] = true;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WTRL");
						}
						else if (ParseNumericArg(argc, argv, i, "--WR", value))
						{
							gpu->hbm2.WR = value;
							gpu->modify[0] = true;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WR");
						}
						else if (ParseNumericArg(argc, argv, i, "--RREFD", value))
						{
							gpu->hbm2.RREFD = value;
							gpu->modify[0] = true;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RREFD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDRDDD", value))
						{
							gpu->hbm2.RDRDDD = value;
							gpu->modify[0] = true;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDRDDD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDRDSD", value))
						{
							gpu->hbm2.RDRDSD = value;
							gpu->modify[0] = true;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDRDSD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDRDSC", value))
						{
							gpu->hbm2.RDRDSC = value;
							gpu->modify[0] = true;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDRDSC");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDRDSCL", value))
						{
							gpu->hbm2.RDRDSCL = value;
							gpu->modify[0] = true;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDRDSCL");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRWRDD", value))
						{
							gpu->hbm2.WRWRDD = value;
							gpu->modify[0] = true;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRWRDD");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRWRSD", value))
						{
							gpu->hbm2.WRWRSD = value;
							gpu->modify[0] = true;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRWRSD");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRWRSC", value))
						{
							gpu->hbm2.WRWRSC = value;
							gpu->modify[0] = true;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRWRSC");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRWRSCL", value))
						{
							gpu->hbm2.WRWRSCL = value;
							gpu->modify[0] = true;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRWRSCL");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRRD", value))
						{
							gpu->hbm2.WRRD = value;
							gpu->modify[0] = true;
							gpu->modify[10] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDWR", value))
						{
							gpu->hbm2.RDWR = value;
							gpu->modify[0] = true;
							gpu->modify[10] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDWR");
						}
						else if (ParseNumericArg(argc, argv, i, "--REF", value))
						{
							gpu->hbm2.REF = value;
							gpu->modify[0] = true;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "REF");
						}
						else if (ParseNumericArg(argc, argv, i, "--MRD", value))
						{
							gpu->hbm2.MRD = value;
							gpu->modify[0] = true;
							gpu->modify[13] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "MRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--MOD", value))
						{
							gpu->hbm2.MOD = value;
							gpu->modify[0] = true;
							gpu->modify[13] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "MOD");
						}
						else if (ParseNumericArg(argc, argv, i, "--XS", value))
						{
							gpu->hbm2.XS = value;
							gpu->modify[0] = true;
							gpu->modify[14] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "XS");
						}
						else if (ParseNumericArg(argc, argv, i, "--XSMRS", value))
						{
							gpu->hbm2.XSMRS = value;
							gpu->modify[0] = true;
							gpu->modify[16] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "XSMRS");
						}
						else if (ParseNumericArg(argc, argv, i, "--PD", value))
						{
							gpu->hbm2.PD = value;
							gpu->modify[0] = true;
							gpu->modify[17] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "PD");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKSRE", value))
						{
							gpu->hbm2.CKSRE = value;
							gpu->modify[0] = true;
							gpu->modify[17] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKSRE");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKSRX", value))
						{
							gpu->hbm2.CKSRX = value;
							gpu->modify[0] = true;
							gpu->modify[17] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKSRX");
						}
						else if (ParseNumericArg(argc, argv, i, "--RFCPB", value))
						{
							gpu->hbm2.RFCPB = value;
							gpu->modify[0] = true;
							gpu->modify[20] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RFCPB");
						}
						else if (ParseNumericArg(argc, argv, i, "--STAG", value))
						{
							gpu->hbm2.STAG = value;
							gpu->modify[0] = true;
							gpu->modify[20] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "STAG");
						}
						else if (ParseNumericArg(argc, argv, i, "--XP", value))
						{
							gpu->hbm2.XP = value;
							gpu->modify[0] = true;
							gpu->modify[21] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "XP");
						}
						else if (ParseNumericArg(argc, argv, i, "--CPDED", value))
						{
							gpu->hbm2.CPDED = value;
							gpu->modify[0] = true;
							gpu->modify[21] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CPDED");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKE", value))
						{
							gpu->hbm2.CKE = value;
							gpu->modify[0] = true;
							gpu->modify[21] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKE");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDDATA", value))
						{
							gpu->hbm2.RDDATA = value;
							gpu->modify[0] = true;
							gpu->modify[22] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDDATA");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRLAT", value))
						{
							gpu->hbm2.WRLAT = value;
							gpu->modify[0] = true;
							gpu->modify[22] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRLAT");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDLAT", value))
						{
							gpu->hbm2.RDLAT = value;
							gpu->modify[0] = true;
							gpu->modify[22] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDLAT");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRDATA", value))
						{
							gpu->hbm2.WRDATA = value;
							gpu->modify[0] = true;
							gpu->modify[22] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRDATA");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKESTAG", value))
						{
							gpu->hbm2.CKESTAG = value;
							gpu->modify[0] = true;
							gpu->modify[23] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKESTAG");
						}
						else if (ParseNumericArg(argc, argv, i, "--RFC", value))
						{
							gpu->hbm2.RFC = value;
							gpu->modify[0] = true;
							gpu->modify[24] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RFC");
						}
					}
					else if (DetermineMemoryType(gpu->dev) == HBM) {
						if (ParseNumericArg(argc, argv, i, "--DAT_DLY0", value))
						{
							gpu->ctl1.hbm.DAT_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_DLY0", value))
						{
							gpu->ctl1.hbm.DQS_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_XTR0", value))
						{
							gpu->ctl1.hbm.DQS_XTR = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_XTR0");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_DLY0", value))
						{
							gpu->ctl1.hbm.OEN_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_EXT0", value))
						{
							gpu->ctl1.hbm.OEN_EXT = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_EXT0");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_SEL0", value))
						{
							gpu->ctl1.hbm.OEN_SEL = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_SEL0");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_DLY0", value))
						{
							gpu->ctl1.hbm.CMD_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_DLY0", value))
						{
							gpu->ctl1.hbm.ADR_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--DAT_DLY1", value))
						{
							gpu->ctl2.hbm.DAT_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_DLY1", value))
						{
							gpu->ctl2.hbm.DQS_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_XTR1", value))
						{
							gpu->ctl2.hbm.DQS_XTR = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_XTR1");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_DLY1", value))
						{
							gpu->ctl2.hbm.OEN_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_EXT1", value))
						{
							gpu->ctl2.hbm.OEN_EXT = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_EXT1");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_SEL1", value))
						{
							gpu->ctl2.hbm.OEN_SEL = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_SEL1");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_DLY1", value))
						{
							gpu->ctl2.hbm.CMD_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_DLY1", value))
						{
							gpu->ctl2.hbm.ADR_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--DAT_DLY2", value))
						{
							gpu->ctl3.DAT_DLY = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_DLY2");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_DLY2", value))
						{
							gpu->ctl3.DQS_DLY = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_DLY2");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_XTR2", value))
						{
							gpu->ctl3.DQS_XTR = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_XTR2");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_DLY2", value))
						{
							gpu->ctl3.OEN_DLY = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_DLY2");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_EXT2", value))
						{
							gpu->ctl3.OEN_EXT = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_EXT2");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_SEL2", value))
						{
							gpu->ctl3.OEN_SEL = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_SEL2");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_DLY2", value))
						{
							gpu->ctl3.CMD_DLY = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_DLY2");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_DLY2", value))
						{
							gpu->ctl3.ADR_DLY = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_DLY2");
						}
						else if (ParseNumericArg(argc, argv, i, "--DAT_DLY3", value))
						{
							gpu->ctl4.DAT_DLY = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_DLY3");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_DLY3", value))
						{
							gpu->ctl4.DQS_DLY = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_DLY3");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_XTR3", value))
						{
							gpu->ctl4.DQS_XTR = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_XTR3");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_DLY3", value))
						{
							gpu->ctl4.OEN_DLY = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_DLY3");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_EXT3", value))
						{
							gpu->ctl4.OEN_EXT = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_EXT3");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_SEL3", value))
						{
							gpu->ctl4.OEN_SEL = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_SEL3");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_DLY3", value))
						{
							gpu->ctl4.CMD_DLY = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_DLY3");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_DLY3", value))
						{
							gpu->ctl4.ADR_DLY = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_DLY3");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKSRE", value))
						{
							gpu->pmg.hbm.CKSRE = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKSRE");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKSRX", value))
						{
							gpu->pmg.hbm.CKSRX = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKSRX");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKE_PULSE", value))
						{
							gpu->pmg.hbm.CKE_PULSE = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKE_PULSE");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKE", value))
						{
							gpu->pmg.hbm.CKE = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKE");
						}
						else if (ParseNumericArg(argc, argv, i, "--SEQ_IDLE", value))
						{
							gpu->pmg.hbm.SEQ_IDLE = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "SEQ_IDLE");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDW", value))
						{
							gpu->ras.RCDW = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDW");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDWA", value))
						{
							gpu->ras.RCDWA = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDWA");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDR", value))
						{
							gpu->ras.RCDR = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDR");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDRA", value))
						{
							gpu->ras.RCDRA = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDRA");
						}
						else if (ParseNumericArg(argc, argv, i, "--RRD", value))
						{
							gpu->ras.RRD = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RC", value))
						{
							gpu->ras.RC = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RC");
						}
						else if (ParseNumericArg(argc, argv, i, "--CL", value))
						{
							gpu->cas.hbm.CL = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CL");
						}
						else if (ParseNumericArg(argc, argv, i, "--W2R", value))
						{
							gpu->cas.hbm.W2R = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "W2R");
						}
						else if (ParseNumericArg(argc, argv, i, "--R2R", value))
						{
							gpu->cas.hbm.R2R = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "R2R");
						}
						else if (ParseNumericArg(argc, argv, i, "--CCDL", value))
						{
							gpu->cas.hbm.CCDL = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CCDL");
						}
						else if (ParseNumericArg(argc, argv, i, "--R2W", value))
						{
							gpu->cas.hbm.R2W = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "R2W");
						}
						else if (ParseNumericArg(argc, argv, i, "--NOPR", value))
						{
							gpu->cas.hbm.NOPR = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "NOPR");
						}
						else if (ParseNumericArg(argc, argv, i, "--NOPW", value))
						{
							gpu->cas.hbm.NOPW = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "NOPW");
						}
						else if (ParseNumericArg(argc, argv, i, "--MRD", value))
						{
							gpu->misc.hbm.MRD = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "MRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RRDL", value))
						{
							gpu->misc.hbm.RRDL = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RRDL");
						}
						else if (ParseNumericArg(argc, argv, i, "--RFC", value))
						{
							gpu->misc.hbm.RFC = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RFC");
						}
						else if (ParseNumericArg(argc, argv, i, "--TRP", value))
						{
							gpu->misc.hbm.TRP = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TRP");
						}
						else if (ParseNumericArg(argc, argv, i, "--RP_RDA", value))
						{
							gpu->misc.hbm.RP_RDA = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RP_RDA");
						}
						else if (ParseNumericArg(argc, argv, i, "--RP_WRA", value))
						{
							gpu->misc.hbm.RP_WRA = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RP_WRA");
						}
						else if (ParseNumericArg(argc, argv, i, "--WDATATR", value))
						{
							gpu->misc2.hbm.WDATATR = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WDATATR");
						}
						else if (ParseNumericArg(argc, argv, i, "--T32AW", value))
						{
							gpu->misc2.hbm.T32AW = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "T32AW");
						}
						else if (ParseNumericArg(argc, argv, i, "--RPAR", value))
						{
							gpu->misc2.hbm.RPAR = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RPAR");
						}
						else if (ParseNumericArg(argc, argv, i, "--WPAR", value))
						{
							gpu->misc2.hbm.WPAR = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WPAR");
						}
						else if (ParseNumericArg(argc, argv, i, "--FAW", value))
						{
							gpu->misc2.hbm.FAW = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "FAW");
						}
						else if (ParseNumericArg(argc, argv, i, "--PA2WDATA", value))
						{
							gpu->misc2.hbm.PA2WDATA = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "P2WDATA");
						}
						else if (ParseNumericArg(argc, argv, i, "--PA2RDATA", value))
						{
							gpu->misc2.hbm.PA2RDATA = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "PA2RDATA");
						}
						else if (ParseNumericArg(argc, argv, i, "--DBR", value))
						{
							gpu->smisc1.hbm.DBR = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DBR");
						}
						else if (ParseNumericArg(argc, argv, i, "--DBW", value))
						{
							gpu->smisc1.hbm.DBW = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DBW");
						}
						else if (ParseNumericArg(argc, argv, i, "--TCSR", value))
						{
							gpu->smisc1.hbm.TCSR = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TCSR");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQR", value))
						{
							gpu->smisc1.hbm.DQR = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQR");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQW", value))
						{
							gpu->smisc1.hbm.DQW = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQW");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADD_PAR", value))
						{
							gpu->smisc1.hbm.ADD_PAR = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADD_PAR");
						}
						else if (ParseNumericArg(argc, argv, i, "--TM", value))
						{
							gpu->smisc1.hbm.TM = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TM");
						}
						else if (ParseNumericArg(argc, argv, i, "--WR", value))
						{
							gpu->smisc1.hbm.WR = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WR");
						}
						else if (ParseNumericArg(argc, argv, i, "--NDS", value))
						{
							gpu->smisc1.hbm.NDS = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "NDS");
						}
						else if (ParseNumericArg(argc, argv, i, "--WL", value))
						{
							gpu->smisc1.hbm.WL = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WL");
						}
						else if (ParseNumericArg(argc, argv, i, "--RL", value))
						{
							gpu->smisc1.hbm.RL = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RL");
						}
						else if (ParseNumericArg(argc, argv, i, "--APRAS", value))
						{
							gpu->smisc1.hbm.APRAS = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "APRAS");
						}
						else if (ParseNumericArg(argc, argv, i, "--BG", value))
						{
							gpu->smisc1.hbm.BG = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "BG");
						}
						else if (ParseNumericArg(argc, argv, i, "--BL", value))
						{
							gpu->smisc1.hbm.BL = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "BL");
						}
						else if (ParseNumericArg(argc, argv, i, "--REF", value))
						{
							gpu->ref.REF = value;
							gpu->modify[10] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "REF");
						}
						else if (ParseNumericArg(argc, argv, i, "--ENB", value))
						{
							gpu->ham.ENB = value;
							gpu->modify[11] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ENB");
						}
						else if (ParseNumericArg(argc, argv, i, "--CNT", value))
						{
							gpu->ham.CNT = value;
							gpu->modify[11] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CNT");
						}
						else if (ParseNumericArg(argc, argv, i, "--TRC", value))
						{
							gpu->ham.TRC = value;
							gpu->modify[11] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TRC");
						}
						else if (ParseNumericArg(argc, argv, i, "--THRESH", value))
						{
							gpu->throt.THRESH = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "THRESH");
						}
						else if (ParseNumericArg(argc, argv, i, "--LEVEL", value))
						{
							gpu->throt.LEVEL = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "LEVEL");
						}
						else if (ParseNumericArg(argc, argv, i, "--PWRDOWN", value))
						{
							gpu->throt.PWRDOWN = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "PWRDOWN");
						}
						else if (ParseNumericArg(argc, argv, i, "--SHUTDOWN", value))
						{
							gpu->throt.SHUTDOWN = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "SHUTDOWN");
						}
						else if (ParseNumericArg(argc, argv, i, "--EN_SHUTDOWN", value))
						{
							gpu->throt.EN_SHUTDOWN = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "EN_SHUTDOWN");
						}
						else if (ParseNumericArg(argc, argv, i, "--OVERSAMPLE", value))
						{
							gpu->throt.OVERSAMPLE = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OVERSAMPLE");
						}
						else if (ParseNumericArg(argc, argv, i, "--AVG_SAMPLE", value))
						{
							gpu->throt.AVG_SAMPLE = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "AVG_SAMPLE");
						}
					}
					else // GDDR5
					{
						if (ParseNumericArg(argc, argv, i, "--DAT_DLY0", value))
						{
							gpu->ctl1.rx.DAT_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_DLY0", value))
						{
							gpu->ctl1.rx.DQS_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_XTR0", value))
						{
							gpu->ctl1.rx.DQS_XTR = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_XTR0");
						}
						else if (ParseNumericArg(argc, argv, i, "--DAT_2Y_DLY0", value))
						{
							gpu->ctl1.rx.DAT_2Y_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_2Y_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_2Y_DLY0", value))
						{
							gpu->ctl1.rx.ADR_2Y_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_2Y_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_2Y_DLY0", value))
						{
							gpu->ctl1.rx.CMD_2Y_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_2Y_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_DLY0", value))
						{
							gpu->ctl1.rx.OEN_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_EXT0", value))
						{
							gpu->ctl1.rx.OEN_EXT = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_EXT0");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_SEL0", value))
						{
							gpu->ctl1.rx.OEN_SEL = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_SEL0");
						}
						else if (ParseNumericArg(argc, argv, i, "--ODT_DLY0", value))
						{
							gpu->ctl1.rx.ODT_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ODT_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--ODT_EXT0", value))
						{
							gpu->ctl1.rx.ODT_EXT = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ODT_EXT0");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_DLY0", value))
						{
							gpu->ctl1.rx.ADR_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_DLY0", value))
						{
							gpu->ctl1.rx.CMD_DLY = value;
							gpu->modify[0] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_DLY0");
						}
						else if (ParseNumericArg(argc, argv, i, "--DAT_DLY1", value))
						{
							gpu->ctl2.rx.DAT_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_DLY1", value))
						{
							gpu->ctl2.rx.DQS_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--DQS_XTR1", value))
						{
							gpu->ctl2.rx.DQS_XTR = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DQS_XTR1");
						}
						else if (ParseNumericArg(argc, argv, i, "--DAT_2Y_DLY1", value))
						{
							gpu->ctl2.rx.DAT_2Y_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DAT_2Y_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_2Y_DLY1", value))
						{
							gpu->ctl2.rx.ADR_2Y_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_2Y_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_2Y_DLY1", value))
						{
							gpu->ctl2.rx.CMD_2Y_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_2Y_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_DLY1", value))
						{
							gpu->ctl2.rx.OEN_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_EXT1", value))
						{
							gpu->ctl2.rx.OEN_EXT = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_EXT1");
						}
						else if (ParseNumericArg(argc, argv, i, "--OEN_SEL1", value))
						{
							gpu->ctl2.rx.OEN_SEL = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "OEN_SEL1");
						}
						else if (ParseNumericArg(argc, argv, i, "--ODT_DLY1", value))
						{
							gpu->ctl2.rx.ODT_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ODT_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--ODT_EXT1", value))
						{
							gpu->ctl2.rx.ODT_EXT = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ODT_EXT1");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR_DLY1", value))
						{
							gpu->ctl2.rx.ADR_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR_DLY2");
						}
						else if (ParseNumericArg(argc, argv, i, "--CMD_DLY1", value))
						{
							gpu->ctl2.rx.CMD_DLY = value;
							gpu->modify[1] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CMD_DLY1");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKSRE", value))
						{
							gpu->pmg.rx.CKSRE = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKSRE");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKSRX", value))
						{
							gpu->pmg.rx.CKSRX = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKSRX");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKE_PULSE", value))
						{
							gpu->pmg.rx.CKE_PULSE = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKE_PULSE");
						}
						else if (ParseNumericArg(argc, argv, i, "--CKE", value))
						{
							gpu->pmg.rx.CKE = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CKE");
						}
						else if (ParseNumericArg(argc, argv, i, "--SEQ_IDLE", value))
						{
							gpu->pmg.rx.SEQ_IDLE = value;
							gpu->modify[2] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "SEQ_IDLE");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDW", value))
						{
							gpu->ras.RCDW = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDW");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDWA", value))
						{
							gpu->ras.RCDWA = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDWA");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDR", value))
						{
							gpu->ras.RCDR = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDR");
						}
						else if (ParseNumericArg(argc, argv, i, "--RCDRA", value))
						{
							gpu->ras.RCDRA = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RCDRA");
						}
						else if (ParseNumericArg(argc, argv, i, "--RRD", value))
						{
							gpu->ras.RRD = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RC", value))
						{
							gpu->ras.RC = value;
							gpu->modify[3] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RC");
						}
						else if (ParseNumericArg(argc, argv, i, "--CL", value))
						{
							gpu->cas.rx.CL = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CL");
						}
						else if (ParseNumericArg(argc, argv, i, "--W2R", value))
						{
							gpu->cas.rx.W2R = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "W2R");
						}
						else if (ParseNumericArg(argc, argv, i, "--R2R", value))
						{
							gpu->cas.rx.R2R = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "R2R");
						}
						else if (ParseNumericArg(argc, argv, i, "--CCDL", value))
						{
							gpu->cas.rx.CCDL = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CCDL");
						}
						else if (ParseNumericArg(argc, argv, i, "--R2W", value))
						{
							gpu->cas.rx.R2W = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "R2W");
						}
						else if (ParseNumericArg(argc, argv, i, "--NOPR", value))
						{
							gpu->cas.rx.NOPR = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "NOPR");
						}
						else if (ParseNumericArg(argc, argv, i, "--NOPW", value))
						{
							gpu->cas.rx.NOPW = value;
							gpu->modify[4] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "NOPW");
						}
						else if (ParseNumericArg(argc, argv, i, "--RFC", value))
						{
							(IsR9(gpu->dev) ? gpu->misc.r9.RFC : gpu->misc.rx.RFC) = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RFC");
						}
						else if (ParseNumericArg(argc, argv, i, "--TRP", value))
						{
							(IsR9(gpu->dev) ? gpu->misc.r9.TRP : gpu->misc.rx.TRP) = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TRP");
						}
						else if (ParseNumericArg(argc, argv, i, "--RP_RDA", value))
						{
							(IsR9(gpu->dev) ? gpu->misc.r9.RP_RDA : gpu->misc.rx.RP_RDA) = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RP_RDA");
						}
						else if (ParseNumericArg(argc, argv, i, "--RP_WRA", value))
						{
							(IsR9(gpu->dev) ? gpu->misc.r9.RP_WRA : gpu->misc.rx.RP_WRA) = value;
							gpu->modify[5] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RP_WRA");
						}
						else if (ParseNumericArg(argc, argv, i, "--WDATATR", value))
						{
							gpu->misc2.rx.WDATATR = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WDATATR");
						}
						else if (ParseNumericArg(argc, argv, i, "--T32AW", value))
						{
							gpu->misc2.rx.T32AW = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "T32AW");
						}
						else if (ParseNumericArg(argc, argv, i, "--WEDC", value))
						{
							gpu->misc2.rx.WEDC = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WEDC");
						}
						else if (ParseNumericArg(argc, argv, i, "--REDC", value))
						{
							gpu->misc2.rx.REDC = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "REDC");
						}
						else if (ParseNumericArg(argc, argv, i, "--FAW", value))
						{
							gpu->misc2.rx.FAW = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "FAW");
						}
						else if (ParseNumericArg(argc, argv, i, "--PA2WDATA", value))
						{
							gpu->misc2.rx.PA2WDATA = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "P2WDATA");
						}
						else if (ParseNumericArg(argc, argv, i, "--PA2RDATA", value))
						{
							gpu->misc2.rx.PA2RDATA = value;
							gpu->modify[6] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "PA2RDATA");
						}
						else if (ParseNumericArg(argc, argv, i, "--WL", value))
						{
							gpu->smisc1.rx.WL = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WL");
						}
						else if (ParseNumericArg(argc, argv, i, "--MR0_CL", value))
						{
							gpu->smisc1.rx.CL = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "MR0_CL");
						}
						else if (ParseNumericArg(argc, argv, i, "--TM", value))
						{
							gpu->smisc1.rx.TM = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TM");
						}
						else if (ParseNumericArg(argc, argv, i, "--WR", value))
						{
							gpu->smisc1.rx.WR = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WR");
						}
						else if (ParseNumericArg(argc, argv, i, "--DS", value))
						{
							gpu->smisc1.rx.DS = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DS");
						}
						else if (ParseNumericArg(argc, argv, i, "--DT", value))
						{
							gpu->smisc1.rx.DT = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "DT");
						}
						else if (ParseNumericArg(argc, argv, i, "--ADR", value))
						{
							gpu->smisc1.rx.ADR = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ADR");
						}
						else if (ParseNumericArg(argc, argv, i, "--CAL", value))
						{
							gpu->smisc1.rx.CAL = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CAL");
						}
						else if (ParseNumericArg(argc, argv, i, "--PLL", value))
						{
							gpu->smisc1.rx.PLL = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "PLL");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDBI", value))
						{
							gpu->smisc1.rx.RDBI = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDBI");
						}
						else if (ParseNumericArg(argc, argv, i, "--WDBI", value))
						{
							gpu->smisc1.rx.WDBI = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WDBI");
						}
						else if (ParseNumericArg(argc, argv, i, "--ABI", value))
						{
							gpu->smisc1.rx.ABI = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ABI");
						}
						else if (ParseNumericArg(argc, argv, i, "--RESET", value))
						{
							gpu->smisc1.rx.RESET = value;
							gpu->modify[7] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RESET");
						}
						else if (ParseNumericArg(argc, argv, i, "--SR", value))
						{
							gpu->smisc2.SR = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "SR");
						}
						else if (ParseNumericArg(argc, argv, i, "--WCK01", value))
						{
							gpu->smisc2.WCK01 = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WCK01");
						}
						else if (ParseNumericArg(argc, argv, i, "--WCK23", value))
						{
							gpu->smisc2.WCK23 = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WCK23");
						}
						else if (ParseNumericArg(argc, argv, i, "--WCK2CK", value))
						{
							gpu->smisc2.WCK2CK = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WCK2CK");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDQS", value))
						{
							gpu->smisc2.RDQS = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDQS");
						}
						else if (ParseNumericArg(argc, argv, i, "--INFO", value))
						{
							gpu->smisc2.INFO = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "INFO");
						}
						else if (ParseNumericArg(argc, argv, i, "--WCK2", value))
						{
							gpu->smisc2.WCK2 = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WCK2");
						}

						else if (ParseNumericArg(argc, argv, i, "--BG", value))
						{
							gpu->smisc2.BG = value;
							gpu->modify[8] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "BG");
						}
						else if (ParseNumericArg(argc, argv, i, "--EDCHP", value))
						{
							gpu->smisc3.EDCHP = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "EDCHP");
						}
						else if (ParseNumericArg(argc, argv, i, "--CRCWL", value))
						{
							gpu->smisc3.CRCWL = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CRCWL");
						}
						else if (ParseNumericArg(argc, argv, i, "--CRCRL", value))
						{
							gpu->smisc3.CRCRL = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CRCRL");
						}
						else if (ParseNumericArg(argc, argv, i, "--RDCRC", value))
						{
							gpu->smisc3.RDCRC = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RDCRC");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRCRC", value))
						{
							gpu->smisc3.WRCRC = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRCRC");
						}
						else if (ParseNumericArg(argc, argv, i, "--EDC", value))
						{
							gpu->smisc3.EDC = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "EDC");
						}
						else if (ParseNumericArg(argc, argv, i, "--RAS", value))
						{
							gpu->smisc3.RAS = value;
							gpu->modify[9] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RAS");
						}
						else if (ParseNumericArg(argc, argv, i, "--CLEHF", value))
						{
							gpu->smisc8.CLEHF = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "CLEHF");
						}
						else if (ParseNumericArg(argc, argv, i, "--WREHF", value))
						{
							gpu->smisc8.WREHF = value;
							gpu->modify[12] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WREHF");
						}
						else if (ParseNumericArg(argc, argv, i, "--ACTRD", value))
						{
							gpu->dram1.ACTRD = value;
							gpu->modify[13] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ACTRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--ACTWR", value))
						{
							gpu->dram1.ACTWR = value;
							gpu->modify[13] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "ACTWR");
						}
						else if (ParseNumericArg(argc, argv, i, "--RASMACTRD", value))
						{
							gpu->dram1.RASMACTRD = value;
							gpu->modify[13] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RASMACTRD");
						}
						else if (ParseNumericArg(argc, argv, i, "--RASMACTWR", value))
						{
							gpu->dram1.RASMACTWR = value;
							gpu->modify[13] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RASMACTWR");
						}
						else if (ParseNumericArg(argc, argv, i, "--RAS2RAS", value))
						{
							gpu->dram2.RAS2RAS = value;
							gpu->modify[14] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RAS2RAS");
						}
						else if (ParseNumericArg(argc, argv, i, "--RP", value))
						{
							gpu->dram2.RP = value;
							gpu->modify[14] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "RP");
						}
						else if (ParseNumericArg(argc, argv, i, "--WRPLUSRP", value))
						{
							gpu->dram2.WRPLUSRP = value;
							gpu->modify[14] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "WRPLUSRP");
						}
						else if (ParseNumericArg(argc, argv, i, "--BUS_TURN", value))
						{
							gpu->dram2.BUS_TURN = value;
							gpu->modify[14] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "BUS_TURN");
						}
						else if (ParseNumericArg(argc, argv, i, "--REF", value))
						{
							gpu->ref.REF = value;
							gpu->modify[15] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "REF");
						}
						else if (ParseNumericArg(argc, argv, i, "--TWT2RT", value))
						{
							gpu->train.TWT2RT = value;
							gpu->modify[16] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TWT2RT");
						}
						else if (ParseNumericArg(argc, argv, i, "--TARF2T", value))
						{
							gpu->train.TARF2T = value;
							gpu->modify[16] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TARF2T");
						}
						else if (ParseNumericArg(argc, argv, i, "--TT2ROW", value))
						{
							gpu->train.TT2ROW = value;
							gpu->modify[16] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TT2ROW");
						}
						else if (ParseNumericArg(argc, argv, i, "--TLD2LD", value))
						{
							gpu->train.TLD2LD = value;
							gpu->modify[16] = true;
							if (gpu->log[0]) strcat(gpu->log, ", ");
							strcat(gpu->log, "TLD2LD");
						}
					}
				}
			}
		}
	}

	// Actually applies the changes, if any.
	for (int index = 0; index < gpuCount; index++)
	{
		GPU* gpu = &gpus[index];
		for (int i = 0; i < _countof(gpu->modify); i++)
		{
			if (gpu->modify[i])
			{
				switch (DetermineMemoryType(gpu->dev))
				{
				case HBM2:
				{
					u32 value = ((u32*)& gpu->hbm2)[i];
					if (i == 0) // special logic for frequency
					{
						value = (gpu->hbm2.frequency == 0x118) ? 0x118 : 0x11C;
					}

					lseek(gpu->mmio, AMD_TIMING_REGS_BASE_1 + (i * sizeof(u32)), SEEK_SET);
					write(gpu->mmio, &value, sizeof(u32));

					lseek(gpu->mmio, AMD_TIMING_REGS_BASE_2 + (i * sizeof(u32)), SEEK_SET);
					write(gpu->mmio, &value, sizeof(u32));

					lseek(gpu->mmio, AMD_TIMING_REGS_BASE_3 + (i * sizeof(u32)), SEEK_SET);
					write(gpu->mmio, &value, sizeof(u32));

					lseek(gpu->mmio, AMD_TIMING_REGS_BASE_4 + (i * sizeof(u32)), SEEK_SET);
					write(gpu->mmio, &value, sizeof(u32));
					break;
				}
				case GDDR5:
					switch (i)
					{
					case 0:
						lseek(gpu->mmio, MC_SEQ_WR_CTL_D0, SEEK_SET);
						write(gpu->mmio, &gpu->ctl1, sizeof(gpu->ctl1.rx));
						break;
					case 1:
						lseek(gpu->mmio, MC_SEQ_WR_CTL_D1, SEEK_SET);
						write(gpu->mmio, &gpu->ctl2, sizeof(gpu->ctl2.rx));
						break;
					case 2:
						lseek(gpu->mmio, MC_SEQ_PMG_TIMING, SEEK_SET);
						write(gpu->mmio, &gpu->pmg, sizeof(gpu->pmg.rx));
						break;
					case 3:
						lseek(gpu->mmio, MC_SEQ_RAS_TIMING, SEEK_SET);
						write(gpu->mmio, &gpu->ras, sizeof(gpu->ras));
						break;
					case 4:
						lseek(gpu->mmio, MC_SEQ_CAS_TIMING, SEEK_SET);
						write(gpu->mmio, &gpu->cas, sizeof(gpu->cas.rx));
						break;
					case 5:
						lseek(gpu->mmio, MC_SEQ_MISC_TIMING, SEEK_SET);
						write(gpu->mmio, &gpu->misc, sizeof(gpu->misc.rx));
						break;
					case 6:
						lseek(gpu->mmio, MC_SEQ_MISC_TIMING2, SEEK_SET);
						write(gpu->mmio, &gpu->misc2, sizeof(gpu->misc2.rx));
						break;
					case 7:
						lseek(gpu->mmio, MC_SEC_MISC1, SEEK_SET);
						write(gpu->mmio, &gpu->smisc1, sizeof(gpu->smisc1.rx));
						break;
					case 8:
						lseek(gpu->mmio, MC_SEC_MISC2, SEEK_SET);
						write(gpu->mmio, &gpu->smisc2, sizeof(gpu->smisc2));
						break;
					case 9:
						lseek(gpu->mmio, MC_SEC_MISC3, SEEK_SET);
						write(gpu->mmio, &gpu->smisc3, sizeof(gpu->smisc3));
						break;
					case 10:
						lseek(gpu->mmio, MC_SEC_MISC4, SEEK_SET);
						write(gpu->mmio, &gpu->smisc4, sizeof(gpu->smisc4));
						break;
					case 11:
						lseek(gpu->mmio, MC_SEC_MISC7, SEEK_SET);
						write(gpu->mmio, &gpu->smisc7, sizeof(gpu->smisc7));
						break;
					case 12:
						lseek(gpu->mmio, MC_SEC_MISC8, SEEK_SET);
						write(gpu->mmio, &gpu->smisc8, sizeof(gpu->smisc8));
						break;
					case 13:
						lseek(gpu->mmio, MC_ARB_DRAM_TIMING, SEEK_SET);
						write(gpu->mmio, &gpu->dram1, sizeof(gpu->dram1));
						break;
					case 14:
						lseek(gpu->mmio, MC_ARB_DRAM_TIMING2, SEEK_SET);
						write(gpu->mmio, &gpu->dram2, sizeof(gpu->dram2));
						break;
					case 15:
						lseek(gpu->mmio, MC_ARB_RFSH_RATE, SEEK_SET);
						write(gpu->mmio, &gpu->ref, sizeof(gpu->ref));
						break;
					case 16:
						lseek(gpu->mmio, MC_SEQ_TRAINING, SEEK_SET);
						write(gpu->mmio, &gpu->train, sizeof(gpu->train));
						break;
					}
					break;
				case HBM:
					switch (i)
					{
					case 0:
						lseek(gpu->mmio, MC_SEQ_WR_CTL_D0_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->ctl1, sizeof(gpu->ctl1.hbm));
						break;
					case 1:
						lseek(gpu->mmio, MC_SEQ_WR_CTL_D1_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->ctl2, sizeof(gpu->ctl2.hbm));
						break;
					case 2:
						lseek(gpu->mmio, MC_SEQ_WR_CTL_D2_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->ctl3, sizeof(gpu->ctl3));
						break;
					case 3:
						lseek(gpu->mmio, MC_SEQ_WR_CTL_D3_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->ctl4, sizeof(gpu->ctl4));
						break;
					case 4:
						lseek(gpu->mmio, MC_SEQ_PMG_TIMING_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->pmg, sizeof(gpu->pmg.hbm));
						break;
					case 5:
						lseek(gpu->mmio, MC_SEQ_RAS_TIMING_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->ras, sizeof(gpu->ras));
						break;
					case 6:
						lseek(gpu->mmio, MC_SEQ_CAS_TIMING_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->cas, sizeof(gpu->cas.hbm));
						break;
					case 7:
						lseek(gpu->mmio, MC_SEQ_MISC_TIMING_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->misc, sizeof(gpu->misc.hbm));
						break;
					case 8:
						lseek(gpu->mmio, MC_SEQ_MISC_TIMING2_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->misc2, sizeof(gpu->misc2.hbm));
						break;
					case 9:
						lseek(gpu->mmio, MC_SEC_MISC1_HBM, SEEK_SET);
						write(gpu->mmio, &gpu->smisc1, sizeof(gpu->smisc1.hbm));
						break;
					case 10:
						lseek(gpu->mmio, MC_ARB_RFSH_RATE, SEEK_SET);
						write(gpu->mmio, &gpu->ref, sizeof(gpu->ref));
						break;
					case 11:
						lseek(gpu->mmio, MC_SEQ_ROW_HAMMER, SEEK_SET);
						write(gpu->mmio, &gpu->ham, sizeof(gpu->ham));
						break;
					case 12:
						lseek(gpu->mmio, MC_THERMAL_THROTTLE, SEEK_SET);
						write(gpu->mmio, &gpu->throt, sizeof(gpu->throt));
						break;
					}
					break;
				}
			}
		}
	}

	for (int index = 0; index < gpuCount; index++)
	{
		GPU* gpu = &gpus[index];
		if (gpu->log[0])
		{
			printf("Successfully applied new %s settings to GPU %d.\n", gpu->log, index);
		}
	}

	pci_cleanup(pci);
	return 0;
}
