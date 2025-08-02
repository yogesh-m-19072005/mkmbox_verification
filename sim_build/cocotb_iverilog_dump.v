module cocotb_iverilog_dump();
initial begin
    $dumpfile("sim_build/mkmbox.fst");
    $dumpvars(0, mkmbox);
end
endmodule
