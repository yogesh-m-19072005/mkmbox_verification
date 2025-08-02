TOPLEVEL_LANG ?= verilog

PWD := $(shell pwd)
TOP_MODULE := mkmbox

VERILOG_SOURCES = \
    $(PWD)/ceg/verilog_core/mkmbox.v \
    $(PWD)/ceg/verilog_core/mkrestoring_div.v \
    $(PWD)/ceg/verilog_core/FIFO2.v \
    $(PWD)/ceg/verilog_core/mkcombo_mul.v \
    $(PWD)/ceg/verilog_core/FIFOL1.v \
    $(PWD)/ceg/verilog_core/signedmul.v


TOPLEVEL := mkmbox
MODULE := test_mbox 

SIM = icarus

include $(shell cocotb-config --makefiles)/Makefile.sim
