import datetime
import sys

import paramiko


host = sys.argv[1]
command = sys.argv[2]

client = paramiko.SSHClient()
client.load_system_host_keys('/Users/Samuel/.ssh/known_hosts')
client.connect(host, username='superuser', password='passw0rd')
stdin, stdout, stderr = client.exec_command(command)

print(f'RUNNING "{command}" on {host}')
print('ERRORS:\n')

for line in stderr:
    sys.stdout.write(line)

print('FORMATTED OUTPUT:\n')

print(f'<cli:Response CommandLine="{command}" ExecutedAt="{datetime.datetime.now().isoformat()}" ExitCode="0" Version="2">')

for line in stdout:
    print(f'<cli:CLIOutput stream="stdout">{line.strip()}</cli:CLIOutput>')

print('</cli:Response>')

# for line in stderr:
#     print(line)
