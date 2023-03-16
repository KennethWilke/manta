`default_nettype none
`timescale 1ns/1ps

module sample_mem(
    input wire clk,

    // fifo
    input wire acquire,
    input wire pop,
    output wire [AW:0] size,

    // probes
    input wire larry,
    input wire curly,
    input wire moe,
    input wire [3:0] shemp,

    // input port
    input wire [15:0] addr_i,
    input wire [15:0] wdata_i,
    input wire [15:0] rdata_i,
    input wire rw_i,
    input wire valid_i,

    // output port
    output reg [15:0] addr_o,
    output reg [15:0] wdata_o,
    output reg [15:0] rdata_o,
    output reg rw_o,
    output reg valid_o);

    parameter BASE_ADDR = 0;
    parameter SAMPLE_DEPTH = 0;

    // bus controller
    reg [$clog2(SAMPLE_DEPTH):0] bram_read_addr;
    reg [15:0] bram_read_data;
    
    always @(*) begin
        // if address is valid
        if ( (addr_i >= BASE_ADDR) && (addr_i <= BASE_ADDR + SAMPLE_DEPTH) ) begin

            // figure out proper place to read from
            // want to read from the read pointer, and then loop back around 
            if(read_pointer + (addr_i - BASE_ADDR) > SAMPLE_DEPTH)
                bram_read_addr <= read_pointer + (addr_i - BASE_ADDR) - SAMPLE_DEPTH;

            else
                bram_read_addr = read_pointer + (addr_i - BASE_ADDR);
        end

        else bram_read_addr <= 0;
    end


    // pipeline bus to compensate for 2-cycles of delay in BRAM
    reg [15:0] addr_pip;
    reg [15:0] wdata_pip;
    reg [15:0] rdata_pip;
    reg rw_pip;
    reg valid_pip;

    always @(posedge clk) begin
        addr_pip <= addr_i;
        wdata_pip <= wdata_i;
        rdata_pip <= rdata_i;
        rw_pip <= rw_i;
        valid_pip <= valid_i;

        addr_o <= addr_pip;
        wdata_o <= wdata_pip;
        rdata_o <= rdata_pip;
        rw_o <= rw_pip;
        valid_o <= valid_pip;

        if( valid_pip && !rw_pip && (addr_pip >= BASE_ADDR) && (addr_pip <= BASE_ADDR + SAMPLE_DEPTH) )
            rdata_o <= bram_read_data;
    end

    
    // bram
    xilinx_true_dual_port_read_first_2_clock_ram #(
		.RAM_WIDTH(16),
		.RAM_DEPTH(SAMPLE_DEPTH),
		.RAM_PERFORMANCE("HIGH_PERFORMANCE")

    ) bram (

		// read port (controlled by bus)
		.clka(clk),
		.rsta(1'b0),
		.ena(1'b1),
		.addra(bram_read_addr),
		.dina(),
		.wea(1'b0),
		.regcea(1'b1),
		.douta(bram_read_data),

		// write port (controlled by FIFO)
		.clkb(clk),
		.rstb(1'b0),
		.enb(1'b1),
		.addrb(write_pointer),
		.dinb({larry, curly, moe, shemp}),
		.web(acquire),
		.regceb(1'b1),
		.doutb());


    // fifo
	localparam AW = $clog2(SAMPLE_DEPTH);

	reg [AW:0] write_pointer = 0;
	reg [AW:0] read_pointer = 0;

	assign size = write_pointer - read_pointer;

	always @(posedge clk) begin
		if (acquire) write_pointer <= write_pointer + 1'd1;
	 	if (pop) read_pointer <= read_pointer + 1'd1;
	end
endmodule

`default_nettype wire