.PHONY: prereqs infra push t0 t1 t2 t3 analyse clean

prereqs:
	bash scripts/00_prereqs_check.sh

infra:
	cd terraform && terraform init && terraform apply -auto-approve
	@echo "Exporting outputs to .env"
	@cd terraform && \
	 echo ACR_NAME=$$(terraform output -raw acr_name)       >  ../.env && \
	 echo LOGIN_SERVER=$$(terraform output -raw login_server) >> ../.env

push:
	bash scripts/10_acr_login.sh
	bash scripts/20_pull_tag_push.sh

t0:
	bash scripts/31_scan_T0.sh
t1:
	bash scripts/32_scan_T1.sh
t2:
	bash scripts/33_scan_T2.sh
t3:
	bash scripts/34_scan_T3.sh

analyse:
	python3 -m pip install -r analysis/requirements.txt
	python3 analysis/merge_and_plot.py

clean:
	rm -rf data/json/* data/csv/* data/fig/*
