# Nodesuite

Nodesuite is a tool to simplify the management and configuration of Leap nodes through the use of [Ansible](https://www.ansible.com/overview/how-ansible-works) playbooks. It is intended to assist Leap node operators and Leap developers get their own Leap nodes up and running quicker and easier. Using Ansible, contributors can aggregate and document best practices and reference material in an executable and standard form.

Nodesuite allows importing and managing a directory of private gitignored configurations that are de-coupled from the Nodesuite project. This allows Nodesuite users to leverage a shared core of functionality, while maintaining operational security and the integrity of private secrets.

**Use Nodesuite to simplify Leap node operations such as:**
* Configure nodeos across environments, networks, and purposes (producer, seed, API).
* Sync from genesis or using a snapshot. Some support for block log download.
* Set up follow on processes automatically for Hyperion, nginx, BP claims, Delphi Oracle, and more.
* Manage sensitive keys and passwords using Ansible Vault in your own private generated repository.
* Setup monitoring & alerting for Nodeos(Leap) to your Slack and/or Pushover.

Tested on Ubuntu 20.04 & 22.04(recommended). Nodesuite is a continual work in progress. 

## Table of Contents
<!--ts-->
  1. [Quick Start](#quick-start)
  1. [Playbooks](#playbooks)
      1. [Testing locally](#testing-locally)
      1. [Usage](#usage)
          1. [Configuration Management](#configuration-management)
	        1. [On securing your sensitive data](#on-securing-your-sensitive-data)
	        1. [Structuring your external configuration repo](#structuring-your-external-repo)
          1. [Command-line Interface Tool](#command-line-interface-tool)
	        1. [Commands](#commands)
	        1. [Setup](#setup)
                  1. [Supported Chains](#supported-chains)
                  1. [Node types](#node-types)
                  1. [Environment selection](#environment-selection)
                  1. [Encryption](#encryption)
                  1. [Default Settings](#default-settings)
          1. [Setting up your private repo](#setting-up-your-private-repo)
  1. [Development Roadmap](#roadmap-todo)
<!--te-->


## Quick Start

Get up and running quickly using the guided setup via the included [command-line tool](#command-line-interface-tool).

### Testing Locally

1. Set up Vagrant locally by installing the latest [Vagrant](https://www.vagrantup.com/downloads.html) & [Virtualbox](https://www.virtualbox.org/wiki/Downloads) versions for your operating system.

1. Install Python3 and Ansible locally (~> v2.8) via package managers.

1. Navigate to the root directory of the repository and run the follow command to bootstrap the dev machine: &nbsp;


&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`vagrant plugin install vagrant-disksize`


&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`vagrant up`

Vagrant should take a minute to spin up and you're ready to run the ansible playbooks!

#### Running ansible playbooks

Once Vagrant is running, you can run playbooks to set up the guest Ubuntu 18.04 virtual machine. For example, to sync a WAX node from genesis on the VM, you could run the following:

```
ansible-playbook -v initialize-leap-genesis-node.yml -i inventories/wax.yml -e "target=dev"
```

this command will look in the `inventories/wax.yml` file for all hosts under the `dev` group, which includes `vagrant`. Then it looks for all of the groups `vagrant` is a host in and uses that to compose the right playbooks to run to configure that particular node. What this means is that adding additional capabilities to your node can be as simple as adding the node's hostname into a particular group and overriding the default configs with your own. If you want to change the type of node being deployed to your Vagrant-managed VM, just modify the groups that `vagrant` is added to in your inventory files.


**Arguments:**

The first argument is the name of the playbook to run.

  -i: passes the inventory file to be used

  -e: overriding variables (target is required to choose a host or group from the inventory file; these are the targeted nodes that the playbook will run against)

  --ask-vault-pass: will prompt for ansible vault password, required when vaulting a secret


## Playbooks

 This project is structured to contain top level Ansible playbooks that are composed of specific Ansible roles. Roles are a way to logically separate functionality into named modules in Ansible. Playbooks can then become a list of roles to include in order to achieve a desired state on a particular node.

The following playbooks are provided to manage various aspects of the node lifecycle, such as: initial setup and configuration of a new host, downloading blockchain blocks and state, updating Leap versions and configs, and replaying a node.

1. *initialize-leap-genesis-node.yml*: Sets up a Leap node, syncing from the first block using a genesis.json file.
2. *initialize-leap-snapshot-node.yml*: Sets up a Leap node, using a provided snapshot file to start syncing at a later block.
3. *initialize-hyperion-genesis-node.yml*: Sets up a Leap node configured for state history, with additional setup and configuration for Hyperion History API. 
4. *update-leap-node.yml*: Restarts a Leap node, applying nodeos version and/or configuration changes.
5. *replay-leap-node.yml*: Restarts and replays a Leap node, applying nodeos version and/or configuration changes.
6. *initialize-system*: Only performs the initialize system step, without performing any Leap-specific functionality.
7. *initialize-nodeos-monitor*: Setup nodeos monitoring & alerting solution via Slack webhook and/or Pushover.

### Roles

As mentioned, roles are modules of functionalty. The roles created to support Nodesuite playbooks include:

1. *initialize_system*: Install system level dependencies, manage deploy user, and set up directory hierarchy.
2. *build_source*: Build or fetch the specified version binaries if they aren't present on the machine.
3. *deploy_node*: Links specified version to deploy directory and refresh configurations and flags for nodeos, then bounce the process. Also set up follow on processes to support Leap-specific use cases, such as Delphi Oracle, BP claiming, and nginx.
4. *hyperion*: Performs additional setup required to run a Hyperion node.


## Usage

### Configuration Management

#### On securing your sensitive data
To ensure the confidentiality of your configurations containing sensitive data, it is recommended that you create a private code repository and clone it into the excluded(i.e. gitignored) **.private/data ** directory found at the root of this repo. After using the [Nodesuite_cli](#command-line-interface-tool) the resulting configurations will be stored in the aforementioned directory.

#### Structuring your external repo

The folder hierarchy of configurations, as generated by the CLI tool guided setup, should be as follows:
```
root/
├── .private/
│   ├── data/
│       ├── inventories/
│       ├── group_vars/
│       ├── stage_vars
│       └── host_vars/
├── *
```

- *inventories*: static inventory files that define hosts and groups those hosts are in.
- *group_vars*: variables inherited by hosts that are members of specified groups.
- *host_vars*: variables inherited by specific, singular hosts.
- *stage_vars*: variables inherited by hosts for specific Leap network environments.

Clone the contents of the ./private/data folder to the root of your external repository to avoid exposing your sensitive data while still being able to pull in upstream changes from the public Nodesuite repository.

Secret variables required by playbooks can be included in an Ansible vault file, which is explained in further detail below.

### Command-line Interface Tool

A CLI tool to manage nodesuite configs. Requires python3 and the packages in `requirements.txt`:

```
pip3 install -r requirements.txt
```

```
Usage: nodesuite_cli.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  bind-repository    Bind an external repository containing private configs.
  config-export      Exports configuration files to specified path.
  config-import      Imports configuration files from specified path.
  config-symlink     Create symlink to specified config folder.
  configure-logging  Set logging level for Nodesuite CLI.
  reset              Wipe existing configurations & links.
  setup              Guided setup: Answer questions to generate configuration YAML files.
  vault-decrypt      Use to decrypt sensitive data via ansible vault.
  vault-encrypt      Use to encrypt sensitive data via ansible vault.
```
_Nodesuite CLI help printout._

#### Commands
 
 Useful commands...

##### Ansible Vault Encryption/Decryption (Your sensitive data!)

```
  vault-decrypt      Use to decrypt sensitive data via ansible vault.
  vault-encrypt      Use to encrypt sensitive data via ansible vault.
```


#### Setup

**Generating your configuration files for the first time?** Start by running the following command at the root directory of this repository:
```
  python3 nodesuite_cli.py setup
```

You will be prompted for information to help configure your hosts as follows:

###### Supported Chains

Select which chain this node will be configured for. Currently supported chains:

- **eos**: the first and largest Leap network.
- **wax**: a commercial Leap network focused on NFT adoption and gaming.
- **fio**:  a customized Leap network focused on improving usability of cryptocurrencies.
- **telos**: a governed Leap network that is cheap to develop on.
- **proton**: a custom Leap network for improving usability of banks.


###### Node Types

Select which type of node you wish to configure:

- **producer**: Block Producer node
- **seed**: Seed node for block propagation
- **v1_history**: Full history API node
- **hyperion**: v2 API node for indexing, storing and retrieving Leap blockchain`s historical data
- **oracle**: Runs Delphi oracle as a follow-on process. 

###### Environment Selection

Select which environment to configure your node for:

- **dev**: Used for local testing purposes.
- **test**: Used to group public testnet nodes.
- **prod**: Used to group public mainnet nodes.

###### Encryption

If you've elected to setup a producer node, you will be prompted to enter your signing keys to be stored within a ansible vault file. You will be prompted to encrypt your vault file (Required when setting up a production node). Encryption will be performed behind the scenes using the `ansible-vault` command. This creates an encrypted file that can be committed to your private data repo, and decrypted using a password when running a nodesuite playbook by using the `--ask-vault-pass` flag.

#### Setting up your private repo

Your custom configuration files generated via the guided setup exist within the `.private/data` directory at the root of this repository. This directory is gitignored.

In order to be able to pull down the latest changes / contribute with ease, a private repository should be initialized within the `.private/data` directory. The guided setup will prompt you to do this.

**Note**: that if you have **pre-existing configuration files** stored in a private repo, you can skip the setup and simple use following command to clone your configuration repo safety into the `.private/data` directory without worrying about accidentally committing your data publicly:&nbsp;

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; `python3 nodesuite_cli.py bind-repository`

#### Default Settings

Work in progress: Explanation of default values generated by the Nodesuite CLI guided setup.

## Roadmap / TODO
There are a lot of potential features that may be added in future versions, based on community feedback and need. Some backlog items include:

- Additional block log archive download and install support
- Dynamic internal and external peering
- Direct integration with some hosting providers (AWS, DigitalOcean) for dynamic inventory management
- Automated firewall configuration
- Ansible quick run mode updates
- Wireguard setup
- Light History
- Programmatic Letsencrypt cert installation
- HAProxy support
- Better documentation

## Credits/Attributions
Deep thanks to all who work tirelessly on improving the Leap ecosystem:

- sw/eden: snapshots, WAX apt package
- amsterdam: block logs, snapshots
- rio: hyperion
- titan, aloha: delphioracle
- cryptolions: various scripts
- greymass: RPC endpoints, nginx configs
- EOS Costa Rica: adopting Nodesuite and spreading the love :)
- And many other individuals and teams working on tools in the Leap community!

###### Disclaimer: EOS Detroit is not responsible for data loss, security issues, mis-configuration of your Leap node, or any other problems stemming from use of this project.