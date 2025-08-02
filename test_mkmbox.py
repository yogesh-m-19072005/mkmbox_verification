import cocotb
import random
import os
import yaml
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.binary import BinaryValue
from cocotb_coverage.coverage import coverage_db, CoverCross, CoverPoint

# -----------------------------------------
# Reference model for multiplier
def multiplier_model(in1, in2, funct3, wordop):
    if funct3 == 0:
        # MUL or MULW
        if wordop:
            # MULW: 32-bit signed × signed, result sign-extended to 64-bit
            in1_s = in1 if in1 < 2**31 else in1 - 2**32
            in2_s = in2 if in2 < 2**31 else in2 - 2**32
            result = (in1_s * in2_s) & 0xFFFFFFFF
            if result & 0x80000000:
                expected = result | 0xFFFFFFFF00000000  # sign-extend
            else:
                expected = result
        else:
            # MUL: 64-bit signed × signed, return low 64 bits
            in1_s = in1 if in1 < 2**63 else in1 - 2**64
            in2_s = in2 if in2 < 2**63 else in2 - 2**64
            expected = (in1_s * in2_s) & 0xFFFFFFFFFFFFFFFF
        return expected

    elif funct3 == 1:
        # MULH: signed × signed, return high 64 bits
        in1_s = in1 if in1 < 2**63 else in1 - 2**64
        in2_s = in2 if in2 < 2**63 else in2 - 2**64
        full = in1_s * in2_s
        expected = (full >> 64) & 0xFFFFFFFFFFFFFFFF
        return expected

    elif funct3 == 2:
        # MULHSU: signed × unsigned, return high 64 bits
        in1_s = in1 if in1 < 2**63 else in1 - 2**64
        in2_u = in2 & 0xFFFFFFFFFFFFFFFF
        full = in1_s * in2_u
        expected = (full >> 64) & 0xFFFFFFFFFFFFFFFF
        return expected

    elif funct3 == 3:
        # MULHU: unsigned × unsigned, return high 64 bits
        in1_u = in1 & 0xFFFFFFFFFFFFFFFF
        in2_u = in2 & 0xFFFFFFFFFFFFFFFF
        full = in1_u * in2_u
        expected = (full >> 64) & 0xFFFFFFFFFFFFFFFF
        return expected

    else:
        return 0  # unsupported funct3




# -----------------------------------------
# Functional coverage points
@CoverPoint("top.funct3", xf=lambda f, *_: f, bins=[0, 1, 2, 3])
@CoverPoint("top.wordop", xf=lambda _, w, *__: w, bins=[0, 1])
@CoverPoint("top.in1", xf=lambda *_a, **__k: _a[2], bins=[0, 1, -1, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000])
@CoverPoint("top.in2", xf=lambda *_a, **__k: _a[3], bins=[0, 1, -1, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000])
@CoverCross("top.cross", items=["top.funct3", "top.wordop"])
def record_coverage(funct3, wordop, in1, in2):
    pass

# -----------------------------------------
@cocotb.test()
async def mkmbox_basic_mul_test(dut):
    """Functional test with corner cases + coverage for mkmbox multiplier"""

    # Setup
    cocotb.start_soon(Clock(dut.CLK, 10, units="ns").start())
    dut.RST_N.value = 0
    dut.EN_ma_inputs.value = 0
    dut.tx_output_enq_rdy_b.value = 1
    dut.tx_output_notFull_b.value = 1
    await RisingEdge(dut.CLK)
    dut.RST_N.value = 1
    await RisingEdge(dut.CLK)

    # Test control
    count = int(os.getenv('COUNT', 100))

    corner_cases = [0, 1, -1, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000]

    for _ in range(count):
        funct3 = random.choice([0, 1, 2, 3])
        wordop = random.choice([0, 1])

        if random.random() < 0.3:
            in1 = random.choice(corner_cases)
            in2 = random.choice(corner_cases)
        else:
            if wordop:
                in1 = random.randint(-(2**31), 2**31 - 1)
                in2 = random.randint(-(2**31), 2**31 - 1)
            else:
                in1 = random.randint(0, 2**64 - 1)
                in2 = random.randint(0, 2**64 - 1)

        packed_input = (wordop << 131) | ((in1 & 0xFFFFFFFFFFFFFFFF) << 67) | ((in2 & 0xFFFFFFFFFFFFFFFF) << 3) | funct3
        dut.ma_inputs_inputs.value = BinaryValue(packed_input, n_bits=132, bigEndian=False)
        dut.EN_ma_inputs.value = 1
        await RisingEdge(dut.CLK)
        dut.EN_ma_inputs.value = 0

        # Wait for result
        while not dut.tx_output_enq_ena.value:
            await RisingEdge(dut.CLK)

        dut_result = dut.tx_output_enq_data.value.integer
        expected = multiplier_model(in1, in2, funct3, wordop)

        # Coverage
        record_coverage(funct3, wordop, in1, in2)

        # Logging
        print(f"[PASS] funct3={funct3} wordop={wordop} in1={in1} in2={in2} => DUT={dut_result} expected={expected}")
        assert dut_result == expected, \
            f"[FAIL] funct3={funct3} wordop={wordop} in1={in1} in2={in2} => DUT={hex(dut_result)} != expected={hex(expected)}"

    # Dump coverage to YAML
    coverage_db.export_to_yaml("mkmbox_mul_coverage.yaml")
    print("[INFO] Functional coverage exported to mkmbox_mul_coverage.yaml")

