.PHONY: demo install validate-icp

demo:
	bash scripts/demo.sh

install:
	pip install -r requirements.txt

validate-icp:
	python scripts/validate_icp.py config/icp.example.yaml
