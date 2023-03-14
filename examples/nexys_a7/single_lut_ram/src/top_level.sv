`default_nettype none
`timescale 1ns / 1ps

module top_level (
	input wire clk,
	input wire btnc,

	output logic [15:0] led,
    output logic ca, cb, cc, cd, ce, cf, cg,
    output logic [7:0] an,

	input wire uart_txd_in,
	output logic uart_rxd_out
	);
	
    // Signal Generator
    // logic [7:0] count;
    // always_ff @(posedge clk) count <= count + 1;
    

    manta manta (
        .clk(clk),

        .rx(uart_txd_in),
        .tx(uart_rxd_out));

    assign led = manta.brx_my_logic_analyzer_addr;

    logic [6:0] cat;
	assign {cg,cf,ce,cd,cc,cb,ca} = cat;
    ssd ssd (
        .clk_in(clk),
        .rst_in(btnc),
        .val_in( (manta.my_logic_analyzer_btx_rdata << 16) | (manta.brx_my_logic_analyzer_wdata) ),
        .cat_out(cat),
        .an_out(an));

endmodule

`default_nettype wire