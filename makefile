up:
	ddev start

down:
	ddev stop

update:
	ddev craft update all --interactive=0 --backup=0

release:
	npx commit-and-tag-version \
  git push

env:
	op inject -f -i .env.tpl -o src/.env; \
	op inject -f -i .env.tpl -o srv/.env; \
	op inject -f -i .env.tpl -o bruno/.env

setup:
	ddev composer install; \
	ddev src npm install

logs:
	ddev logs -f

#* DEV
prettier:
	npx prettier@3 --write .; \
	git add .; \
	git commit -m "chore: prettier"; \
	git push

pint:
	

#* UTILS
purge:
	sh .utils/purge.sh

types:
	clear; \
	python .utils/generate_types.py