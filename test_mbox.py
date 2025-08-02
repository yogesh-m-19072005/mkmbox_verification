import cocotb
import random
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.binary import BinaryValue
from cocotb_coverage.coverage import coverage_db, CoverPoint, CoverCross

# ---------------------
# Multiplier reference model
def multiplier_model(in1, in2, funct3, wordop):
    if funct3 == 0:  # MUL
        if wordop:
            in1 &= 0xFFFFFFFF
            in2 &= 0xFFFFFFFF
            in1 = in1 if in1 < 2**31 else in1 - 2**32
            in2 = in2 if in2 < 2**31 else in2 - 2**32
            res = in1 * in2
            return res & 0xFFFFFFFF if res >= 0 else (res + (1 << 32)) | 0xFFFFFFFF00000000
        else:
            in1 = in1 if in1 < 2**63 else in1 - 2**64
            in2 = in2 if in2 < 2**63 else in2 - 2**64
            return (in1 * in2) & 0xFFFFFFFFFFFFFFFF

    elif funct3 == 1:  # MULH
        in1 = in1 if in1 < 2**63 else in1 - 2**64
        in2 = in2 if in2 < 2**63 else in2 - 2**64
        return ((in1 * in2) >> 64) & 0xFFFFFFFFFFFFFFFF

    elif funct3 == 2:  # MULHSU
        in1 = in1 if in1 < 2**63 else in1 - 2**64
        return ((in1 * in2) >> 64) & 0xFFFFFFFFFFFFFFFF

    elif funct3 == 3:  # MULHU
        return ((in1 * in2) >> 64) & 0xFFFFFFFFFFFFFFFF
    else:
        return 0

# ---------------------
# Divider reference model
def divider_model(in1, in2, funct3, wordop):
    mask32 = 0xFFFFFFFF
    mask64 = 0xFFFFFFFFFFFFFFFF
    if in2 == 0:
        return -1 if funct3 in [4, 5, 6] else mask64
    if funct3 == 4:  # DIV
        if wordop:
            in1 &= mask32
            in2 &= mask32
            in1 = in1 if in1 < 2**31 else in1 - 2**32
            in2 = in2 if in2 < 2**31 else in2 - 2**32
            return (in1 // in2) & mask32
        else:
            in1 = in1 if in1 < 2**63 else in1 - 2**64
            in2 = in2 if in2 < 2**63 else in2 - 2**64
            return (in1 // in2) & mask64

    elif funct3 == 5:  # DIVU
        return (in1 // in2) & (mask32 if wordop else mask64)

    elif funct3 == 6:  # REM
        if wordop:
            in1 = in1 if in1 < 2**31 else in1 - 2**32
            in2 = in2 if in2 < 2**31 else in2 - 2**32
            return (in1 % in2) & mask32
        else:
            in1 = in1 if in1 < 2**63 else in1 - 2**64
            in2 = in2 if in2 < 2**63 else in2 - 2**64
            return (in1 % in2) & mask64

    elif funct3 == 7:  # REMU
        return (in1 % in2) & (mask32 if wordop else mask64)
    else:
        return 0

# ---------------------
# Coverage
corner_cases = [
    0x00000000, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000,
    0x00000001, 0xFFFFFFFE, 0x0000FFFF, 0xFFFF0000,
    0x00010000, 0xDEADBEEF, 0x12345678, 0xCAFEBABE,
    0xFFFFFFFFFFFFFFFF, 0x8000000000000000, 0x7FFFFFFFFFFFFFFF
]

@CoverPoint("top.funct3", xf=lambda f, *_: f, bins=list(range(8)), at_least=1)
@CoverPoint("top.wordop", xf=lambda _, w, *__: w, bins=[0, 1], at_least=1)
@CoverPoint("top.in1", xf=lambda *_a, **__k: _a[2], bins=corner_cases, at_least=1)
@CoverPoint("top.in2", xf=lambda *_a, **__k: _a[3], bins=corner_cases, at_least=1)
@CoverCross("top.cross", items=["top.funct3", "top.wordop"], at_least=1)
def record_coverage(funct3, wordop, in1, in2):
    pass

# ---------------------
@cocotb.test()
async def mkmbox_full_test(dut):
    cocotb.start_soon(Clock(dut.CLK, 10, units="ns").start())
    dut.RST_N.value = 0
    dut.EN_ma_inputs.value = 0
    dut.tx_output_enq_rdy_b.value = 1
    dut.tx_output_notFull_b.value = 1
    await RisingEdge(dut.CLK)
    dut.RST_N.value = 1
    await RisingEdge(dut.CLK)

    seen = set()
    max_iter = 10000
    iter_count = 0
    last_coverage = -10  # force 0% print at start

    while coverage_db["top"].coverage < 100.0 and iter_count < max_iter:
        found = False
        for wordop in [0, 1]:
            for funct3 in range(8):
                for in1 in corner_cases:
                    for in2 in corner_cases:
                        packed = (wordop << 131) | ((in1 & 0xFFFFFFFFFFFFFFFF) << 67) | ((in2 & 0xFFFFFFFFFFFFFFFF) << 3) | funct3
                        if packed in seen:
                            continue
                        seen.add(packed)
                        found = True
                        break
                    if found: break
                if found: break
            if found: break

        if not found:
            # fallback: random unique input
            wordop = random.randint(0, 1)
            funct3 = random.randint(0, 7)
            bits = 32 if wordop else 64
            in1 = random.getrandbits(bits)
            in2 = random.getrandbits(bits)
            packed = (wordop << 131) | ((in1 & 0xFFFFFFFFFFFFFFFF) << 67) | ((in2 & 0xFFFFFFFFFFFFFFFF) << 3) | funct3
            if packed in seen:
                continue
            seen.add(packed)

        # Drive inputs
        dut.ma_inputs_inputs.value = BinaryValue(packed, n_bits=132, bigEndian=False)
        dut.EN_ma_inputs.value = 1
        await RisingEdge(dut.CLK)
        dut.EN_ma_inputs.value = 0

        # Wait for output ready with timeout
        for _ in range(20):
            if dut.tx_output_enq_ena.value:
                break
            await RisingEdge(dut.CLK)

        # Read DUT result
        mask = 0xFFFFFFFF if wordop else 0xFFFFFFFFFFFFFFFF

        if wordop:
            # 32-bit word operation - signed integer and then mask
            dut_result = dut.tx_output_enq_data.value.signed_integer & mask
        else:
            # 64-bit operation - unsigned integer
            dut_result = dut.tx_output_enq_data.value.integer & mask

        # Get expected result from reference models
        if funct3 < 4:
            expected = multiplier_model(in1, in2, funct3, wordop) & mask
        else:
            expected = divider_model(in1, in2, funct3, wordop) & mask

        # Masked comparison to handle signed/unsigned differences
        if (dut_result & mask) != (expected & mask):
            raise AssertionError(
                f"[FAIL] funct3={funct3} wordop={wordop} in1=0x{in1:X} in2=0x{in2:X} "
                f"=> DUT=0x{(dut_result & mask):X} != expected=0x{(expected & mask):X}"
            )
        else:
            print(f"[PASS] funct3={funct3} wordop={wordop} in1=0x{in1:X} in2=0x{in2:X} => result=0x{(dut_result & mask):X}")

        # Record coverage for this vector
        record_coverage(funct3, wordop, in1, in2)

        iter_count += 1

        current_coverage = int(coverage_db["top"].coverage)
        if current_coverage >= last_coverage + 10:
            print(f"[INFO] Coverage reached {current_coverage:.1f}%")
            last_coverage = current_coverage

    # Final coverage report and export
    coverage_db.report_coverage(cocotb.log.info, bins=True)
    coverage_db.export_to_yaml("mkmbox_full_coverage.yaml")
    print("[INFO] Final coverage report written to mkimbox_full_coverage.yaml")

