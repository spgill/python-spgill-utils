# stdlib imports
import pathlib
import subprocess
import time

# vendor imports
import click
import click_shell
import colorama as clr
import pymongo
from ..chassis import Chassis


# Make sure colorama is initialized
clr.init(autoreset=True)


class Tunneler:
    def __init__(self):
        # Create the chassis
        self.chassis = Chassis(
            root=pathlib.Path(__file__).parent,
            proxy="~/.spgill.util.tunnel.json",
            props={
                "MONGODB_URI": None,
                "CONNECTIONS": [],
                "GATEWAY_USER": None,
                "GATEWAY_ADDRESS": None,
                "GATEWAY_PORT": None,
            },
        )

        # If not mongodb uri is configured, raise an exception because it's required
        mongoUri = self.chassis.props.MONGODB_URI.value
        if not mongoUri:
            raise RuntimeError(
                f"No MongoDB URI configured. Check '{self.chassis.store.proxy}'"
            )

        # Connect to the database
        print("Connecting to database...")
        self.client = pymongo.MongoClient(mongoUri)
        self.db = self.client.live

        # Retrieve the currently configured connections from config
        self.connections = self.chassis.shelf.get("CONNECTIONS", [])

        # Fetch initial target information
        print("Starting up...")
        self.fetchTargets()
        print("Ready.")

        # Start shell loop
        self.proc = None
        self.startLoop()

    def startLoop(self):
        # Define the root shell object
        @click_shell.shell(
            prompt=f"tunneler{clr.Fore.GREEN}${clr.Style.RESET_ALL} "
        )
        def shell():
            pass

        # List command
        @shell.command(name="list")
        def shell_list():
            self.listTargets()
            self.listConnections()

        # Add command
        @shell.command(name="add")
        @click.argument("index", type=int)
        @click.argument("local", type=str)
        def shell_add(index, local):
            self.addConnection(index, local)

        # Delete command
        @shell.command(name="del")
        @click.argument("marker", type=str)
        def shell_delete(marker):
            self.delConnection(marker)

        # Start connection command
        @shell.command(name="start")
        @click.option("--wait", is_flag=True)
        def shell_start(wait):
            self.startTunnel(wait)

        # Stop connection command
        @shell.command(name="stop")
        def shell_stop():
            self.stopTunnel()

        # Start up the shell
        shell()

    def syncBack(self):
        self.chassis.shelf["CONNECTIONS"] = self.connections
        self.chassis.shelf.sync()

    def alphaIndex(self, n):
        n += 1
        string = ""

        while n > 0:
            n, remainder = divmod(n - 1, 26)
            string = chr(65 + remainder) + string

        return string

    def fetchTargets(self):
        """Query the database for enough information to make connections work"""
        self.targets = {}
        self.targetChoices = {}
        count = 0

        for machine in self.db.machines.find({}).sort("address"):
            # Unpack some variables
            machineAddress = machine["address"]

            portList = machine.get("ports", [])
            targetPortList = list(
                filter(lambda p: p.get("target", False), portList)
            )

            self.targets[machineAddress] = {}

            if len(targetPortList) == 0:
                continue

            for portInfo in targetPortList:
                self.targets[machineAddress][portInfo["internal"]] = portInfo[
                    "label"
                ]

                count += 1

                self.targetChoices[count] = [
                    machine["address"],
                    portInfo["internal"],
                ]

    def listTargets(self):
        print("Querying database for targets...")

        self.fetchTargets()
        count = 0

        for machine in self.db.machines.find({}).sort("address"):
            # Unpack some variables
            machineAddress = machine["address"]

            header = (
                f"{clr.Back.WHITE}{clr.Fore.BLACK} {machineAddress} {clr.Style.RESET_ALL} "
                f"{machine['name']} "
            )
            targetPreamble = ""

            if machine.get("hostname", None):
                header += f"({clr.Fore.YELLOW}{machine['hostname']}{clr.Style.RESET_ALL})"
                targetPreamble += f"({clr.Fore.YELLOW}{machine['hostname']}{clr.Style.RESET_ALL}) "

            portList = machine.get("ports", [])
            targetPortList = list(
                filter(lambda p: p.get("target", False), portList)
            )

            if len(targetPortList) == 0:
                continue

            print(header)

            for portInfo in targetPortList:

                count += 1
                countLabel = str(count).rjust(2)

                print(
                    f"    ({clr.Fore.CYAN}{countLabel}{clr.Style.RESET_ALL}) "
                    f"{portInfo['internal']} : {portInfo['label']}"
                )

            print()

    def listConnections(self):
        print("\nCurrently configured connections:")

        if not len(self.connections):
            print(f"{clr.Fore.RED}NONE{clr.Style.RESET_ALL}")

        for i, conn in enumerate(self.connections):
            # print(self.alphaIndex(i), line)
            alpha = self.alphaIndex(i).rjust(2)
            print(
                f"({clr.Fore.MAGENTA}{alpha}{clr.Style.RESET_ALL}) "
                f"{clr.Back.WHITE}{clr.Fore.BLACK} {conn[0]}:{conn[1]} {clr.Style.RESET_ALL} "
                f"-> localhost:{clr.Fore.YELLOW}{conn[2]}{clr.Style.RESET_ALL}"
            )

        print()

    def addConnection(self, index, localPort):
        print(
            "Attempting to map target "
            f"{clr.Fore.CYAN}{index}{clr.Style.RESET_ALL} "
            "to local port "
            f"{clr.Fore.YELLOW}{localPort}{clr.Style.RESET_ALL}..."
        )

        if index not in self.targetChoices:
            print(f"{clr.Fore.RED}Does not exist!{clr.Style.RESET_ALL}")
            return

        targetInfo = self.targetChoices[index]

        # Double check this connection doesn't already exist
        for i, conn in enumerate(self.connections):
            if conn[0] == targetInfo[0] and conn[1] == targetInfo[1]:
                print(
                    f"{clr.Fore.RED}This target is already mapped to connection {clr.Style.RESET_ALL}"
                    f"{clr.Fore.MAGENTA}{self.alphaIndex(i)}{clr.Style.RESET_ALL}"
                )
                return

        self.connections.append([*targetInfo, localPort])
        self.syncBack()

        self.listConnections()

    def delConnection(self, marker):
        # Make sure them marker is uppercase
        marker = marker.upper()

        # Cycle through all connection looking for a matching marker
        for i, conn in enumerate(self.connections):
            alpha = self.alphaIndex(i)

            # If they match, then we have a hit
            if alpha == marker:
                print(
                    f"Removing connection "
                    f"{clr.Fore.MAGENTA}{marker}{clr.Style.RESET_ALL}..."
                )

                self.connections.pop(i)
                self.syncBack()

                self.listConnections()

                return

        # If the command did not return, then no connection was found
        print(
            f"{clr.Fore.RED}Connection{clr.Style.RESET_ALL} "
            f"{clr.Fore.MAGENTA}{marker}{clr.Style.RESET_ALL} "
            f"{clr.Fore.RED}was not found{clr.Style.RESET_ALL}"
        )

    def startTunnel(self, wait):
        # Ensure there isn't already an ssh process running
        if self.proc and self.proc.poll() is None:
            print(
                f"{clr.Fore.RED}SSH tunnel is already running!{clr.Style.RESET_ALL}"
            )
            return

        # Make sure we have the necessary props to open an SSH connection
        gatewayUser = self.chassis.props.GATEWAY_USER.value
        gatewayAddress = self.chassis.props.GATEWAY_ADDRESS.value
        gatewayPort = self.chassis.props.GATEWAY_PORT.value

        if not gatewayUser or not gatewayAddress or not gatewayPort:
            print(
                f"{clr.Fore.RED}Invalid gateway connection information. Check props file.{clr.Style.RESET_ALL}"
            )

        # Start constructing the ssh command
        args = ["ssh", "-N"]

        # Add each port tunnel
        for conn in self.connections:
            args.append("-L")
            args.append(f"{conn[2]}:{conn[0]}:{conn[1]}")

        # Disable host key checking
        args += [
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "StrictHostKeyChecking=no",
        ]

        # Add address information
        args += [f"{gatewayUser}@{gatewayAddress}", "-p", str(gatewayPort)]

        # Start the ssh connection
        print("Starting SSH connection...")
        self.proc = subprocess.Popen(args)
        time.sleep(3)

        # If waiting is desired, wait for any key to kill the ssh process
        if wait:
            print(
                f"{clr.Fore.GREEN}Press any key to kill connection...{clr.Style.RESET_ALL}"
            )
            click.getchar()
            self.proc.kill()

    def stopTunnel(self):
        if self.proc:
            if self.proc.poll() is None:
                print("Terminating SSH tunnel...")
                self.proc.kill()
            else:
                print("SSH tunnel has already been terminated")
        else:
            print(
                f"{clr.Fore.RED}SSH tunnel was never started!{clr.Style.RESET_ALL}"
            )


# Initiate the main method
if __name__ == "__main__":
    Tunneler()
