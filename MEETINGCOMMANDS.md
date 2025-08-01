vagrant up
vagrant ssh
python3 nodesuite_cli.py setup
ansible-playbook -v initialize-system.yml -i inventories/eos.yml -e "target=vagrant" --ask-vault-pass


put this into /etc/vbox/networks.conf
* 10.0.1.0/24