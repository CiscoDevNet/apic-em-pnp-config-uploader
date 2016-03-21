# apic-em-pnp-config-uploader
Tool for the APIC-EM PnP App to add devices and upload their configs

# Usage
```usage
apic-em-pnp-config-uploader.py [-h] -s SERVER -u USERNAME -p PASSWORD
                                      [-d] [--clear-site]
                                      [filelist [filelist ...]]

Upload configs to APIC-EM and create corresponding ZTD rules.

Positional arguments:
  filelist              Config file(s) or path to config files (need to end in
                        .txt)

Optional arguments:
  -h, --help            show this help message and exit
  -s SERVER, --server SERVER
                        Server hostname or IP of APIC-EM
  -u USERNAME, --username USERNAME
                        Username to login to APIC-EM
  -p PASSWORD, --password PASSWORD
                        Password to login to APIC-EM
  -d, --debug           Enable debug mode
  --clear-site          Clear all rules from site first
```

Example: ./apic-em-pnp-config-uploader.py -s 10.0.0.1 -u admin -p cisco switch1.txt

# Sample Config
This tool needs some additional information about the device it is going to add, like serial number, model (i.e. SKU) and site/project name. Furthermore, the config needs to contain a hostname. The filename of config files needs to end in .txt.

Minimal working config file:

```sample-config
!! Needed for APIC-EM PNP !!
! SERIAL FAC00000001
! SITE SITE1
! MODEL WS-C2960S-F48TS-L
!! -------------------- !!
!
hostname Switch1
!
! [...]
!
```