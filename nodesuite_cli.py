import click
import yaml
import sys, os, shutil
import logging
from datetime import datetime
from os import path
import ast
from enum import Enum
from getpass import getpass
import subprocess

global_config_path = '.private/cli_settings.config'

class LoggingLevelEnum(Enum):
    DEBUG    = 10
    INFO     = 20
    WARNING  = 30
    ERROR    = 40
    CRITICAL = 50

class TokenEnum(Enum):
    eos    = 'EOS'
    fio    = 'FIO'
    telos  = 'TLOS'
    wax    = 'WAXP'
    proton = 'XPR'
class EnvironmentEnum(Enum):
    dev  = 'dev'
    test = 'test'
    prod = 'prod'

class NodeTypeEnum(Enum):
    producer   = 'producer'
    seed       = 'seed'
    v1_history = 'v1_history'
    hyperion   = 'hyperion'

class VaultOperationEnum(Enum):
    encrypt = 'encrypt'
    decrypt = 'decrypt'

class Host:
    def __init__(self, hostname, host_ip, host_user, node_type, api_endpoint=None):
        self.hostname     = hostname
        self.host_ip      = host_ip
        self.host_user    = host_user
        self.node_type    = node_type
        self.api_endpoint = api_endpoint

def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '')

def confirmationPrompt():
    prompt = click.getchar()
    click.echo(prompt)
    if(prompt.lower() == 'y'):
        return True
    elif(prompt.lower() == 'n'):
        return False
    else: 
        return confirmationPrompt()
        
def selectInt():
    try:
        s = click.getchar()
        return int(s)
    except ValueError:
        return selectInt()

@click.group()
def main():
    pass

@click.command('setup', help='Guided setup: Answer questions to generate configurations.')
@click.option('--overwrite', '-o', count=True)
@click.option('--export', '-e')
def setupCommand(export, overwrite):
    global base_dir
    global host_list
    global token, environment, selected_node_types
    global vault_rabbitmq_password, vault_es_api_basic_auth_password
    vault_rabbitmq_password = None
    vault_es_api_basic_auth_password = None
    selected_node_types = []
    host_list = []

    if export != None:
        base_dir = export
    else:
        base_dir = '.private/data'

    if(overwrite == 1):
        overwrite = True
        logger.info('Force overwrite ENABLED.')
    else:
        overwrite = False

    click.echo('Running setup wizard...\n')
    logger.info('Running guided setup...')

    click.echo('==Supported Chains==')
    i = 1
    for t in TokenEnum:
        click.echo(f'[{i}] {t.name}')
        i += 1

    click.echo('Select chain: ', nl=False)
    s = selectInt()
    while(s > len(TokenEnum) or s < 1):
        click.echo('[ERROR] Invalid selection!')
        click.echo('Select chain: ', nl=False)
        s = selectInt()
        
    token = selectItem(TokenEnum, s)
    click.echo(f'{token.name}\n')
    logger.info(f'selected token: {token.name}')

    click.echo('==Environment==')
    i = 1
    for t in EnvironmentEnum:
        click.echo(f'[{i}] {t.name}')
        i += 1

    click.echo('Select environment: ', nl=False)
    s = selectInt()
    while(s > len(EnvironmentEnum) or s < 1):
        click.echo('[ERROR] Invalid selection!')
        click.echo('Select environment: ', nl=False)
        s = selectInt()
        
    environment = selectItem(EnvironmentEnum, s)
    click.echo(f'{environment.name}\n')
    logger.info(f'environment: {environment.name}')

    inventory = initializeInventory()

    inventory_base_dir = path.join(base_dir, 'inventories')
    os.makedirs(inventory_base_dir, exist_ok=True)

    yaml.add_representer(type(None), represent_none)
    
    if((path.exists(f'{inventory_base_dir}/{token.name}.yml')) and (overwrite == 0)):
        click.echo(f'[WARNING] {inventory_base_dir}/{token.name}.yml already exists. Overwrite[y/n]?', nl=False)
        prompt = confirmationPrompt()
        if prompt == False:
            logger.info(f'Terminating setup. User declined file overwrite. - {inventory_base_dir}/{token.name}.yml')
            sys.exit('Exiting...')
    else:
        f = open(f'{inventory_base_dir}/{token.name}.yml', 'w+')
        f.write('---\n')
        f.write(yaml.dump(inventory))
        f.close()

    try:
        group_vars_base = path.join(base_dir, 'group_vars')
        os.makedirs(path.join(group_vars_base, environment.name), exist_ok=True)
        os.makedirs(path.join(group_vars_base, token.name), exist_ok=True)
        os.makedirs(path.join(group_vars_base, NodeTypeEnum.producer.name), exist_ok=True)
        os.makedirs(path.join(group_vars_base, NodeTypeEnum.seed.name), exist_ok=True)
        os.makedirs(path.join(group_vars_base, NodeTypeEnum.v1_history.name), exist_ok=True)
        os.makedirs(path.join(group_vars_base, NodeTypeEnum.hyperion.name), exist_ok=True)
        os.makedirs(path.join(group_vars_base, 'nginx'), exist_ok=True)

        if(NodeTypeEnum.hyperion in selected_node_types):
            vault_rabbitmq_password = getpass('[Hyperion] Enter default RabbitMQ Password: ')
            vault_es_api_basic_auth_password = getpass('[Hyperion] Enter default ElasticSearch API Password: ')
        setDefaultGroupVars(group_vars_base, overwrite)
        setEnvironmentGroupVars(group_vars_base, environment.name, overwrite)
        setInventoryGroupVars(group_vars_base, overwrite)

        stage_vars_dir = path.join(base_dir, 'stage_vars', token.name)
        os.makedirs(path.join(stage_vars_dir, environment.name), exist_ok=True) 
        
        setEnvironmentStageVars(stage_vars_dir, environment.name, overwrite)
        setEnvironmentSigningKeys(stage_vars_dir, environment.name, overwrite)

        all_config_path = initializeConfig(path.join(group_vars_base, 'all'), overwrite)
        configureDefaultsAll(all_config_path, overwrite)

        if base_dir != None:
            if(path.islink('group_vars')): 
                os.remove('group_vars')
            if(path.islink('stage_vars')): 
                os.remove('stage_vars')
            if(path.islink('host_vars')): 
                os.remove('host_vars')
            if(path.islink('inventories')): 
                os.remove('inventories')
            configureSymlinks(base_dir, overwrite)

        click.echo('\n==Configurations generated successfully!==\n\n')
        logger.info('Setup: Configurations generated. Yay!')

        click.echo('Your custom configuration files generated via the guided setup exist within the `.private/data` directory at the root of this repository. This directory is gitignored.\n')
        click.echo('In order to be able to pull down the latest changes / contribute with ease, a private repository should be created containing the contents of said directory.\n')
        click.echo('Would you like assistance in doing so [y/n]?', nl=False)
        
        prompt = confirmationPrompt()
        if prompt == False:
            logger.info(f'Setup complete. User declined automated private repo setup.')
            sys.exit('Setup complete!')
        else:
            setupPrivateRepository()

    except Exception as ex:
        click.echo(f'[ERROR] During setup: {ex}')
        sys.exit()

def setupPrivateRepository():
    command = 'git init .private/data'
    bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output = bash.communicate()
    
    os.chdir('.private/data')
    command = 'git add *'
    bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output = bash.communicate()

    command = 'git commit -m initialize'
    bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output = bash.communicate()

    url = input('Please enter the URL to your remote repository(ex:git@gitlab.com:eosbrodawg/my-private-repo.git ): ')

    command = f'git remote add origin {url}'
    bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output = bash.communicate()

    command = 'git push -u origin master'
    bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output = bash.communicate()

    print(output)

def selectItem(enum, x):
    i = 1
    options = {}
    for t in (enum):
        options[i] = t
        i += 1
    return options[x]

#TODO: prompt when duplicate hostname provided.
def defineHosts(inventory):
    hostname = ' '
    while(hostname != ''):
        hostname = input(f'[{environment.name}] Enter host name (leave blank to continue): ')
        if(hostname == ''):
            break
        host_ip = input('Enter ansible host IP: ')
        host_user = input('Enter ansible host user (leave blank to default to \'root\'): ')
        host_user = host_user if host_user else 'root'
        
        click.echo(f'==Select Node Type for [{hostname}]==')
        i = 1
        for t in NodeTypeEnum:
            click.echo(f'[{i}] {t.name}')
            i += 1

        click.echo('Select node type: ', nl=False)
        s = selectInt()
        while(s > len(NodeTypeEnum) or s < 1):
            click.echo('[ERROR] Invalid selection!')
            click.echo('Select node type: ', nl=False)
            s = selectInt()
        
        node_type = selectItem(NodeTypeEnum, s)
        click.echo(f'{node_type.name}\n')
        logger.info(f'selected node type: {node_type.name}')

        if((node_type == NodeTypeEnum.v1_history) or (node_type == NodeTypeEnum.hyperion)):
            api_endpoint = input('Enter API endpoint: ')
        else:
            api_endpoint = None
        
        os.makedirs(f'{base_dir}/host_vars', exist_ok=True)
        f = open(f'{base_dir}/host_vars/{hostname}.yml', 'w+')
        f.write('---\n')
        f.close()

        selected_node_types.append(node_type)

        click.echo('Host registered.')

        host = Host(hostname, host_ip, host_user, node_type, api_endpoint)
        host_list.append(host)

        if(node_type == NodeTypeEnum.producer):
            break
        else:
            click.echo('Register another host?', nl=False)
            s = confirmationPrompt()
            if(s == False):
                break

    for host in host_list:
        inventory['all']['children'][token.name]['children'][environment.name]['hosts'][host.hostname] = {}
        inventory['all']['children'][token.name]['children'][environment.name]['hosts'][host.hostname]['ansible_host'] = host.host_ip
        inventory['all']['children'][token.name]['children'][environment.name]['hosts'][host.hostname]['ansible_user'] = host.host_user
        
        if((host.node_type == NodeTypeEnum.v1_history) or (host.node_type == NodeTypeEnum.hyperion)):
            inventory['all']['children'][token.name]['children'][environment.name]['hosts'][host.hostname]['api_endpoint'] = api_endpoint

        try:
            inventory['all']['children'][host.node_type.name]['hosts'][host.hostname] = None
        except KeyError:
            inventory['all']['children'][host.node_type.name] = {
                'hosts': {
                    host.hostname: None
                }
            }

        try:
            if(host.node_type == NodeTypeEnum.hyperion):
                inventory['all']['children']['nginx']['hosts'][host.hostname] = None
        except KeyError:
                inventory['all']['children']['nginx'] = {
                'hosts': {
                    host.hostname: None
                }
            }

def setDefaultGroupVars(base_dir, overwrite):
    config_path = initializeConfig(path.join(base_dir, NodeTypeEnum.producer.name, 'vars.yml'), overwrite)
    f = open(config_path, 'a+')
    assignDefaultsByGroup(NodeTypeEnum.producer.name, f)
    f.close()

    config_path = initializeConfig(path.join(base_dir, NodeTypeEnum.v1_history.name, 'vars.yml'), overwrite)
    f = open(config_path, 'a+')
    assignDefaultsByGroup(NodeTypeEnum.v1_history.name, f)
    f.close()

    config_path = initializeConfig(path.join(base_dir, NodeTypeEnum.hyperion.name, 'vars.yml'), overwrite)
    f = open(config_path, 'a+')
    assignDefaultsByGroup(NodeTypeEnum.hyperion.name, f)
    f.close()

    config_path = initializeConfig(path.join(base_dir, 'nginx', 'vars.yml'), overwrite)
    f = open(config_path, 'a+')
    assignDefaultsByGroup('nginx', f)
    f.close()

    config_path = initializeConfig(path.join(base_dir, NodeTypeEnum.seed.name, 'vars.yml'), overwrite)
    assignDefaultsByGroup('seed', f)
    f.close()

def assignDefaultsByGroup(group, f):
    with open('./data/defaults', 'r') as file:
        try:
            defaults = yaml.load(file, Loader=yaml.FullLoader)
            for default in defaults[group]:
                f.write(f'{default}: {defaults[group][default]}\n')
        except Exception as e:
            click.echo(f'[Error] Exception thrown while retrieving group variable defaults: {e}' )

def setEnvironmentGroupVars(base_dir, environment, overwrite):
    initializeConfig(path.join(base_dir, environment, 'vars.yml'), overwrite)
    f = open(path.join(base_dir, environment, 'vars.yml'), 'a+')

    #TODO: query for additional config vars?    
    f.write(f'stage: {environment}\n')
    if(environment == 'dev'):
        chain_state_db_size = 8192
        f.write(f'chain_state_db_size_mb: {chain_state_db_size}\n')
        jvm_heap_size = '4g'
        f.write(f'jvm_heap_size: {jvm_heap_size}\n')
    f.close()

def setInventoryGroupVars(base_dir, overwrite):
    global token
    initializeConfig(path.join(base_dir, token.name, 'vars.yml'), overwrite)  

    f = open(path.join(base_dir, token.name, 'vars.yml'), 'a+')
    with open('./data/defaults', 'r') as file:
        defaults = yaml.load(file, Loader=yaml.FullLoader)
        for default in defaults[token.name]:
            pass
            f.write(f'{default}: {defaults[token.name][default]}\n')

def setEnvironmentStageVars(base_dir, environment, overwrite):
    initializeConfig(path.join(base_dir, environment, 'vars.yml'), overwrite)

    f = open(path.join(base_dir, environment,'vars.yml'), 'a+')
    with open('./data/chain_ids', 'r') as file:
        try:
            chain_ids = yaml.load(file, Loader=yaml.FullLoader)
            f.write(f'chain_id: {chain_ids[token.name][environment]}\n')
        except Exception as e:
            logging.error(f'{e}')

    #TODO: Dynamic peer list sourcing/validation?
    f.write('peers:\n')
    with open(f'./data/peers/{token.name}/{environment}/current.peers', 'r') as peers:
        try:
            for peer in peers:
                if 'str' in peer:
                    break
                elif(len(peer)>1):
                    if("\n" in peer):
                        f.write(f' - {peer}')
                    else:
                        f.write(f' - {peer}\n')

        except Exception as e:
            logging.error(f'{e}')

    f.write('snapshot_base_url: \n')
    f.write('snapshot_file: \n')
    f.write('snapshot_provider: \n')
    f.write('private_signing_key: \'{{ vault_private_signing_key }}\'\n')


def setEnvironmentSigningKeys(base_dir, environment, overwrite):
    initializeConfig(path.join(base_dir, environment, 'vault.yml'), overwrite)
    with open(path.join(base_dir, environment,'vault.yml'), 'a+') as f:
        pub_key = ''
        priv_key = ''
        if(NodeTypeEnum.producer in selected_node_types):
            pub_key = getpass(f'Enter public signing key [environment: {environment}]: ')
            priv_key = getpass(f'Enter private signing key [environment: {environment}]: ')
            with open(path.join(base_dir, environment, 'vars.yml' ), 'a+') as stage_vars:
                stage_vars.write(f'public_signing_key: {pub_key}\n')
        f.write(f'vault_private_signing_key: {priv_key}\n')    

        if(NodeTypeEnum.hyperion in selected_node_types):
            f.write(f'vault_rabbitmq_password: {vault_rabbitmq_password}\n')
            f.write(f'vault_es_api_basic_auth_password: {vault_es_api_basic_auth_password}\n')

    if((environment == 'prod') and (NodeTypeEnum.producer in selected_node_types)):
        click.echo('Encrypt your secrets (ansible-vault) now!')
        manageVault(VaultOperationEnum.encrypt.value, environment, token.name)
    elif(NodeTypeEnum.producer in selected_node_types):
        click.echo('Encrypt signing keys[y\\n]?')
        prompt = confirmationPrompt()
        if(prompt == True):
            manageVault(VaultOperationEnum.encrypt.value, environment, token.name)
        else:
            click.echo('[WARNING] It is highly recommended that you encrypt your signing keys (vault.yml) at rest!')
    
    click.echo('*Tip: Manage vault file encryption using the CLI vault-encrypt / vault-decrypt commands.')

def initializeInventory():
    inventory = {
        'all': {
            'children': {
                token.name: {
                    'children': {}
                }
            }
        }
    }
    
    click.echo(f'Configure hosts for [{environment.name}]...')
    logger.info(f'Configure hosts for [{environment.name}]...')

    if(environment.name == 'dev'):
        inventory['all']['children'][environment.name] = {}
        inventory['all']['children'][environment.name]['hosts'] = {}
        inventory['all']['children'][environment.name]['hosts']['vagrant'] = {
            'ansible_host': '10.50.0.2',
            'ansible_user': 'vagrant',
            'ansible_ssh_private_key_file': '.vagrant/machines/default/virtualbox/private_key',
            'api_endpoint': 'testnet.eos.local'
        }
        inventory['all']['children'][token.name]['children'][environment.name] = None
        click.echo('[environment: dev] selected. Generating default host.')
    else:
        inventory['all']['children'][token.name]['children'][environment.name] = {}
        inventory['all']['children'][token.name]['children'][environment.name]['hosts'] = {}
        defineHosts(inventory)
        
    click.echo(f'[{environment.name}] environment created!\n')
    logger.info(f'[{environment.name}] environment created!')
    return inventory

def initializeConfig(config_path, overwrite):
    if((path.exists(config_path)) and (overwrite == 0)):
        click.echo(f'[WARNING] {config_path} already exists. Overwrite[y/n]?')
        prompt = confirmationPrompt()
        if prompt == False:
            sys.exit('Exiting...')

    f = open(config_path, "w+")
    f.write('---\n')
    f.close()

    return config_path

def configureDefaultsAll(config_path, overwrite):
    f = open(config_path, 'a+')
    with open('./data/defaults', 'r') as file:
        try:
            defaults = yaml.load(file, Loader=yaml.FullLoader)
            for default in defaults['all']:
                f.write(f'{default}: {defaults["all"][default]}\n')
        except Exception as e:
            sys.exit(e)
    f.close()

@click.command('vault-encrypt', help='Use to encrypt sensitive data via ansible vault.')
@click.option('environmentParam', '--environment', '-e')
@click.option('tokenParam', '--token', '-t')
def vaultEncryptCommand(environmentParam, tokenParam):
    logger.info('[Vault Management] Running VaultEncryptCommand...')
    manageVault(VaultOperationEnum.encrypt.value, environmentParam, tokenParam)
    
@click.command('vault-decrypt', help='Use to decrypt sensitive data via ansible vault.')
@click.option('environmentParam', '--environment', '-e')
@click.option('tokenParam', '--token', '-t')
def vaultDecryptCommand(environmentParam, tokenParam):
    logger.info('[Vault Management] Running VaultDecryptCommand...')
    manageVault(VaultOperationEnum.decrypt.value, environmentParam, tokenParam)

def manageVault(operation, environment, token):
    if not(environment):
        click.echo('==Environments==')
        i = 1
        for t in EnvironmentEnum:
            click.echo(f'[{i}] {t.name}')
            i += 1

        click.echo('Select environment: ', nl=False)
        s = selectInt()
        while(s > len(EnvironmentEnum) or s < 1):
            click.echo('[ERROR] Invalid selection!')
            click.echo('Select environment: ', nl=False)
            s = selectInt()
        
        environment = selectItem(EnvironmentEnum, s).name
        click.echo(environment)
        logger.info(f'[Vault Management] Environment selected: {environment}')

    if not(token):
        click.echo('\n\n==Supported Chains==')
        i = 1
        for t in TokenEnum:
            click.echo(f'[{i}] {t.name}')
            i += 1

        click.echo('Select token: ', nl=False)
        s = selectInt()
        while(s > len(TokenEnum) or s < 1):
            click.echo('[ERROR] Invalid selection!')
            click.echo('Select token: ', nl=False)
            s = selectInt()
        
        token = selectItem(TokenEnum, s).name
        click.echo(token)

    command = f'ansible-vault {operation} .private/data/stage_vars/{token}/{environment}/vault.yml'
    bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)

    return bash.communicate()

@click.command('config-export', help='Exports configuration files to specified path.')
@click.argument('destination_path', type=click.Path(exists=False))
@click.option('--overwrite', '-o', count=True, help='Force overwrite of existing files.')
def configurationExportCommand(destination_path, overwrite):
    shutil.copytree('./inventories', f'{destination_path}/inventories')

@click.command('config-import', help='Imports configuration files from specified path.')
@click.argument('source_path', type=click.Path(exists=True))
@click.option('--overwrite', '-o', count=True, help='Force overwrite of existing files.')
def configurationImportCommand(source_path, overwrite):
    try:
        user_dirs = os.listdir(source_path)
        user_configs = validateConfigs(source_path, user_dirs)
        for dir in user_configs:
            recursiveOverwrite(f'{source_path}/{dir}', dir)
    except Exception as ex:
        raise(ex)
    
def validateConfigs(root_dir, user_dirs):
    required_dirs = ['inventories', 'group_vars', 'stage_vars']
    existing_dirs = []

    for dir in required_dirs:
        if dir in user_dirs:
            click.echo(f'[./{dir}] directory found...')
            for root, sub_dirs, files in os.walk(f'{root_dir}{dir}'):
                if(len(files) < 1):
                    click.echo(f'[WARNING] [./{root}/{dir}] contains no files!')
                else:
                    click.echo(f'[SUCCESS] [./{root}/{dir}] configs located.')
                    existing_dirs.append(dir)
        else:
            logger.error(f'[Configuration Import] Expected directory [./{dir}] not found.')
            sys.exit(f'[ERROR] Expected directory [./{dir}] not found.')

    return existing_dirs

def recursiveOverwrite(src, dest, ignore=None):
    if path.isdir(src):
        if not path.isdir(dest):
            os.makedirs(dest)
        files = os.listdir(src)
        if ignore is not None:
            ignored = ignore(src, files)
        else:
            ignored = set()
        for f in files:
            if f not in ignored:
                recursiveOverwrite(path.join(src, f), path.join(dest, f), ignore)
    else:
        shutil.copyfile(src, dest)

@click.command('config-symlink', help='Create symlink to specified config folder.')
@click.argument('source_path', type=click.Path(exists=True))
@click.option('--overwrite', '-o', count=True, help='Force overwrite of existing files.')
def configureSymlinksCommand(source_path, overwrite = 0):
    configureSymlinks(source_path, overwrite)

def configureSymlinks(source_path, overwrite = 0):
    click.echo('Creating symlinks to new configurations...')
    logger.info('Creating symlinks to new configurations...')

    default_directories = ['stage_vars', 'group_vars', 'inventories', 'host_vars']

    try:
        for x in (default_directories if source_path == '.private/data' else os.listdir(source_path)):
            if os.path.isdir(f'.private/data/{x}') and not x.startswith('.'):
                if overwrite == 1:
                    if path.exists(x):
                        #now = datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
                        #shutil.move(x, f'./_backup_{now}')
                        os.remove(x)
                    elif path.islink(x) or path.isfile(x):
                        os.remove(x)
                os.symlink(f'{source_path}/{x}', x)
                click.echo(f'symlink created: {x} -> {source_path}/{x}')
    except Exception as ex:
        logger.error(f'Exception thrown running configureSymlinks: {ex}')
        sys.exit(f'Exception thrown running configureSymlinks: {ex}')        

@click.command('reset', help='Wipe existing configurations & links.')
def resetCommand():
    logger.warning('Running reset...')
    click.echo('\n[WARNING] This will destroy any existing configurations! Are you sure[y\\n]?', nl=False)
    s = confirmationPrompt()
    click.echo('\n\n')

    click.echo('\n[WARNING] Did you actually read that warning though[y\\n]???', nl=False)
    s = confirmationPrompt()
    click.echo('\n\n')

    if(s != True):
        sys.exit('\nTerminating.')
    
    click.echo('Nuking configurations...')
    if(path.islink('group_vars')): 
        os.remove('group_vars')
    if(path.islink('stage_vars')): 
        os.remove('stage_vars')
    if(path.islink('host_vars')): 
        os.remove('host_vars')
    if(path.islink('inventories')): 
        os.remove('inventories')
    if(path.exists('.private/data')):
        shutil.rmtree('.private/data')

    logger.info('Configurations nuked!')

@click.command('bind-repository', help='Bind an external repository containing private configs.')
@click.argument('repository')
def bindRepositoryCommand(repository):
    logger.info('Running bind repository...')
    if(path.exists('.private/data')):
        click.echo('Files exist in .private folder. Overwrite?')
        logger.debug('Prompting for file overwrite')
        s = confirmationPrompt()
        if(s):
            logger.debug('User confirmed existing file overwrite.')
            command = f'rm -rf .private/data'
            bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
            output, error = bash.communicate()
            if(error):
                logger.error(f'Error removing existing files. Aborting bind repository - {error}')
                sys.exit(f'{error} Exiting...')

    command = f'git clone {repository} .private/data'
    bash = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    
    output, error = bash.communicate()
    if(error):
        click.echo(error)
        logger.error(error)
    logger.info('Config repository cloned into NodeSuite (./.private/data).')

    configureSymlinks('.private/data', 1)

@click.command('configure-logging', help='Set logging level for NodeSuite CLI.')
def configureLoggingCommand():
    logger.debug('Running configureLoggingCommand...')
    click.echo('==Logging Levels==')
    i = 1
    for t in LoggingLevelEnum:
        click.echo(f'[{i}] {t.name}')
        i += 1

    click.echo('Select Logging Level: ', nl=False)
    s = selectInt()
    while(s > len(LoggingLevelEnum) or s < 1):
        click.echo('[ERROR] Invalid selection!')
        click.echo('Select Logging Level: ', nl=False)
        s = selectInt()
        
    logging_level = selectItem(LoggingLevelEnum, s)
    click.echo(f'{logging_level.name}\n')
    logger.info(f'[Configure Logging] Selected logging level: {logging_level.name}')
    setConfiguration('logging_level', logging_level.value)

def getLoggingConfiguration(key):
    try:
        yaml.add_representer(type(None), represent_none)
        if(path.exists(global_config_path) and (os.stat(global_config_path).st_size > 0)):
            with open(global_config_path, 'r') as file:
                try:
                    settings = yaml.load(file, Loader=yaml.FullLoader)

                    return settings['logging']['logging_level']
                except Exception as e:
                    logger.error(f'{e}\nResetting logging configuration.')

                    return configureDefaultLogging()
        else:
            return configureDefaultLogging()
    except Exception as ex:
        logger.error(ex)

def configureDefaultLogging():
    config = {
            'logging': {
                'logging_level': LoggingLevelEnum.INFO.value
            }
        }

    with open(global_config_path, 'w') as file:
        yaml.dump(config, file)

    return LoggingLevelEnum.INFO.value

def setConfiguration(key, value, section = 'logging'):
    if(path.exists(global_config_path)):
        with open(global_config_path) as file:
            config_data = yaml.load(file, Loader=yaml.FullLoader)
            config_data[section][key] = value
        with open(global_config_path, 'w') as file:
            yaml.dump(config_data, file)
    else:
        config = {
            section: {
                key: value
                }
            }
        with open(global_config_path, 'w') as file:
            yaml.dump(config, file)

# Wizard
main.add_command(setupCommand)

# Configurations
main.add_command(configurationExportCommand)
main.add_command(configurationImportCommand)
main.add_command(configureSymlinksCommand)
main.add_command(bindRepositoryCommand)
main.add_command(resetCommand)

# Encryption
main.add_command(vaultEncryptCommand)
main.add_command(vaultDecryptCommand)

#Logging
main.add_command(configureLoggingCommand)

# Initialize logging
logger = logging.getLogger('nodesuite_cli')
logger.setLevel(getLoggingConfiguration('logging_level'))
formatter = logging.Formatter('[%(levelname)s][%(asctime)s] %(name)s: %(message)s')
handler = logging.FileHandler('.private/cli_logging.log')
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)

if __name__ == '__main__':
    main()
