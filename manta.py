from sys import argv
import os
import json
import yaml
from datetime import datetime
import serial


debug = True
version = "0.0.0"


def load_source_files(path):
    """concatenates the list of files provided into a single string"""
    source_files = [
        f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))
    ]
    source_files = [f for f in source_files if f.split(".")[-1] in ["sv", "v"]]

    buf = ""
    for source_file in source_files:
        with open(path + source_file, "r") as f:
            buf += f.read()

    return buf


downlink_template = load_source_files("src/")


def load_config(path):
    """Take path to configuration file, and retun the configuration as a python list/dict object."""
    extension = path.split(".")[-1]

    if "json" in extension:
        with open(path, "r") as f:
            config = json.load(f)

        return config

    elif "yaml" in extension or "yml" in extension:
        with open(path, "r") as f:
            config = yaml.safe_load(f)

        return config

    else:
        raise ValueError("Unable to recognize configuration file extension.")


def check_config(config):
    """Takes a list/dict python object representing a core configuration and throws an error if it is misconfigured."""

    assert (
        "downlink" in config or "uplink" in config
    ), "No downlink or uplink specified."

    if "downlink" in config:
        dl = config["downlink"]
        assert dl[
            "sample_depth"
        ], "Downlink core specified, but sample_depth not specified."
        assert dl[
            "clock_freq"
        ], "Downlink core specified, but clock_freq not specified."
        assert (
            dl["probes"] and len(dl["probes"]) > 0
        ), "Downlink core specified, but no probes specified."
        assert (
            dl["triggers"] and len(dl["triggers"]) > 0
        ), "Downlink core specified, but no triggers specified."

        # confirm core clock is sufficiently fast
        prescaler = dl["clock_freq"] // config["uart"]["baudrate"]
        assert prescaler >= 2

        # confirm actual baudrate and target baudrate are within 5%
        actual_baudrate = config["downlink"]["clock_freq"] / prescaler
        baudrate_error = (
            abs(actual_baudrate - config["uart"]["baudrate"])
            / config["uart"]["baudrate"]
        )
        assert (
            baudrate_error <= 0.05
        ), f"Unable to match target baudrate! Actual baudrate differs from target by {round(100*baudrate_error, 2)}%"

        if debug:
            print(f"UART interface on debug core will the following configuration:")
            print(f' - target_baudrate: {config["uart"]["baudrate"]}')
            print(f" - prescaler: {prescaler}")
            print(f" - actual_baudrate: {round(actual_baudrate, 2)}")

    if "uplink" in config:
        raise NotImplementedError(
            "Cannot check configuration validity for uplinks just yet!"
        )

    if "uart" in config:
        uart = config["uart"]

        # confirm number of data bits is valid
        assert "data" in uart, "Number of data bits in UART interface not specified."
        assert uart["data"] in [8, 7, 6, 5], "Invalid number of data bits."

        # confirm number of stop bits is valid
        assert uart["stop"] in [1, 1.5, 2], "Invalid number of stop bits."

        # confirm parity is valid
        assert uart["parity"] in [
            "none",
            "even",
            "odd",
            "mark",
            "space",
        ], "Invalid parity setting."


def gen_downlink_core(config):
    buf = downlink_template
    dl = config["downlink"]

    # add timestamp
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    buf = buf.replace("@TIMESTAMP", timestamp)

    # add user
    user = os.environ.get("USER", os.environ.get("USERNAME"))
    buf = buf.replace("@USER", user)

    # add trigger
    trigger = [f"({trigger})" for trigger in dl["triggers"]]
    trigger = " || ".join(trigger)
    buf = buf.replace("@TRIGGER", trigger)

    # add concat
    concat = [name for name in dl["probes"]]
    concat = ", ".join(concat)
    concat = "{" + concat + "};"
    buf = buf.replace("@CONCAT", concat)

    # add probes
    probe_verilog = []
    for name, width in dl["probes"].items():
        if width == 1:
            probe_verilog.append(f"input wire {name},")

        else:
            probe_verilog.append(f"input wire [{width-1}:0] {name},")

    probe_verilog = "\n\t".join(probe_verilog)
    buf = buf.replace("@PROBES", probe_verilog)

    # add sample width
    sample_width = sum([width for name, width in dl["probes"].items()])
    buf = buf.replace("@SAMPLE_WIDTH", str(sample_width))

    # add sample depth
    buf = buf.replace("@SAMPLE_DEPTH", str(dl["sample_depth"]))

    # uart config
    buf = buf.replace("@DATA_WIDTH", str(config["uart"]["data"]))
    buf = buf.replace("@BAUDRATE", str(config["uart"]["baudrate"]))
    buf = buf.replace("@CLK_FREQ_HZ", str(dl["clock_freq"]))

    return buf


def print_help():
    help = f"""
Manta v{version} - An In-Situ Debugging Tool for Programmable Hardware

Supported commands:
    gen [config file]       generate the core specified in the config file
    run [config file]       run the core specified in the config file
    terminal [config file]  present a minicom-like serial terminal with the UART settings in the config file
    ports                   list all available serial ports
    help                    display this help message
    ray                     display a splash screen (hehe...splash screen)
    """
    print(help)


def print_ray():
    color_ray = f"""
\033[96m               (\.-./)
\033[96m               /     \\
\033[96m             .'   :   '.
\033[96m        _.-'`     '     `'-._       \033[34;49;1m | \033[34;49;1m Manta v{version} \033[00m
\033[96m     .-'          :          '-.    \033[34;49;1m | \033[34;49;3m An In-Situ Debugging Tool for Programmable Hardware \033[00m
\033[96m   ,'_.._         .         _.._',  \033[34;49;1m | \033[34;49m https://github.com/fischermoseley/manta \033[00m
\033[96m   '`    `'-.     '     .-'`
\033[96m             '.   :   .'            \033[34;49;1m | \033[34;49;3m fischerm [at] mit.edu \033[00m
\033[96m               \_. ._/
\033[96m         \       |^|
\033[96m          |      | ;
\033[96m          \\'.___.' /
\033[96m           '-....-'  \033[00m"""
    print(color_ray)


def setup_serial(ser, config):
    ser.baudrate = config["uart"]["baudrate"]
    ser.port = config["uart"]["port"]
    ser.timeout = config["uart"]["timeout"]

    # setup number of data bits
    if config["uart"]["data"] == 8:
        ser.bytesize = serial.EIGHTBITS

    elif config["uart"]["data"] == 7:
        ser.bytesize = serial.SEVENBITS

    elif config["uart"]["data"] == 6:
        ser.bytesize = serial.SIXBITS

    elif config["uart"]["data"] == 5:
        ser.bytesize = serial.FIVEBITS

    else:
        raise ValueError("Invalid number of data bits in UART configuration.")

    # setup number of stop bits
    if config["uart"]["stop"] == 1:
        ser.stopbits = serial.STOPBITS_ONE

    elif config["uart"]["stop"] == 1.5:
        ser.stopbits = serial.STOPBITS_ONE_POINT_FIVE

    elif config["uart"]["stop"] == 2:
        ser.stopbits = serial.STOPBITS_TWO

    else:
        raise ValueError("Invalid number of stop bits in UART configuration.")

    # setup parity
    if config["uart"]["parity"] == "none":
        ser.parity = serial.PARITY_NONE

    elif config["uart"]["parity"] == "even":
        ser.parity = serial.PARITY_EVEN

    elif config["uart"]["parity"] == "odd":
        ser.parity = serial.PARITY_ODD

    elif config["uart"]["parity"] == "mark":
        ser.parity = serial.PARITY_MARK

    elif config["uart"]["parity"] == "space":
        ser.parity = serial.PARITY_SPACE

    else:
        raise ValueError("Invalid parity setting in UART configuration.")


def read_serial(config):
    # obtain bytestream from FPGA
    with serial.Serial() as ser:
        setup_serial(ser, config)
        ser.open()
        ser.flushInput()
        ser.write(b"\x30")
        data = ser.read(4096)

    return data


def part_select(data, width):
    top, bottom = width

    assert top >= bottom

    mask = 2 ** (top - bottom + 1) - 1
    return (data >> bottom) & mask


def make_widths(config):
    # {probe0, probe1, probe2}
    # [12, 1, 3] should produce
    # [ (11,0) , (12, 12), (15,13) ]

    widths = list(config["probes"].values())

    parts = []
    for i, width in enumerate(widths):
        if i == 0:
            parts.append((width - 1, 0))

        else:
            parts.append(((parts[i - 1][1] + width), (parts[i - 1][1] + 1)))

    # reversing this list is a little bit of a hack, should fix/document
    return parts[::-1]


def export_waveform(config, data, path):
    extension = path.split(".")[-1]

    if extension == "vcd":
        from vcd import VCDWriter

        vcd_file = open(path, "w")
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        with VCDWriter(
            vcd_file, timescale="10 ns", date=timestamp, version="manta"
        ) as writer:
            # add probes to vcd file
            vcd_probes = []
            for name, width in config["probes"].items():
                probe = writer.register_var("ila", name, "wire", size=width)
                vcd_probes.append(probe)

            # calculate bit widths for part selecting
            widths = make_widths(config)

            # slice data, and dump to vcd file
            for timestamp, value in enumerate(data):
                for probe_num, probe in enumerate(vcd_probes):
                    val = part_select(value, widths[probe_num])
                    writer.change(probe, timestamp, val)

        vcd_file.close()

    else:
        raise NotImplementedError("More file formats to come!")


if __name__ == "__main__":
    # print help menu if no args passed or help menu requested
    if len(argv) == 1 or argv[1] == "help":
        print_help()
        exit()

    # open minicom-like serial terminal with given config
    elif argv[1] == "terminal":
        assert len(argv) == 3, "Not enough (or too many) config files specified."

        # TODO: make this work with a looser config file - it should work even if we just have a uart definition
        config = load_config(argv[2])
        check_config(config)

        raise NotImplementedError("Miniterm console is still under development!")

    # list available serial ports
    elif argv[1] == "ports":
        import serial.tools.list_ports

        for info in serial.tools.list_ports.comports():
            print(info)

    # show splash screen
    elif argv[1] == "ray":
        print_ray()
        exit()

    # generate the specified core
    elif argv[1] == "gen":
        assert (
            len(argv) == 4
        ), "Wrong number of arguments, only a config file and output file must both be specified."
        config = load_config(argv[2])
        check_config(config)

        with open(argv[3], "w") as f:
            f.write(gen_downlink_core(config))

    # run the specified core
    elif argv[1] == "run":
        assert (
            len(argv) == 4
        ), "Wrong number of arguments, only a config file and output file must both be specified."
        config = load_config(argv[2])
        check_config(config)

        data = read_serial(config)
        export_waveform(config, data, argv[3])

    else:
        print("Option not recognized.")
        print_help()