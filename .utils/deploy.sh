#!/bin/bash

# Exit on error
set -e

devVERSION="v$npm_package_version"
git checkout production --quiet

echo "Switching to production branch"
prodVERSION=$npm_package_version
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
WEBSITE="$npm_package_name"

echo ""
echo "-----------------------------------------------"
echo "Website:\t $WEBSITE"
echo "Version:\t $devVERSION"
echo "GIT branch:\t $BRANCH"
echo "-----------------------------------------------"
echo ""

if [ $devVERSION = $prodVERSION ]; then
echo "              *** WARNING ***"
echo "    App version is the same on main as on"
echo "   the production branch. Did you remember"
echo "            to npm run release?"
echo ""
echo "-----------------------------------------------"
echo ""

fi

read -p "Do you wish to deploy to the above environment? " yn

if echo "$yn" | grep -iq "^y" ; then
  echo ""
	echo "Will do!"
	echo "-----------------------------------------------"
	echo "Deploying..."

	#Mergin main into production branch
	git merge "$devVERSION"
	#Push it to the repo
  git push origin production --quiet --tags
  echo "-----------------------------------------------"
  echo ""
  echo "Deployed successfully to Git"
  echo ""
else
  echo ""
  echo "-----------------------------------------------"
  echo ""
	echo "Ok, aborting..."
	echo ""
fi

echo "-----------------------------------------------"
echo ""
echo "Switching back to main branch"
git checkout main --quiet
git push origin main --quiet --tags
echo ""
echo "-----------------------------------------------"
echo ""
echo "The deployment is now over. You win. Go back to"
echo "the recovery annex. For your cake"
echo ""
echo "            ,:/+/-"
echo "            /M/              .,-=;//;-"
echo "       .:/= ;MH/,    ,=/+%$XH@MM#@:"
echo "      -$##@+$###@H@MMM#######H:.    -/H#"
echo " .,H@H@ X######@ -H#####@+-     -+H###@X"
echo "  .,@##H;      +XM##M/,     =%@###@X;-"
echo "X%-  :M##########$.    .:%M###@%:"
echo "M##H,   +H@@@$/-.  ,;$M###@%,          -"
echo "M####M=,,---,.-%%H####M$:          ,+@##"
echo "@##################@/.         :%H##@$-"
echo "M###############H,         ;HM##M$="
echo "#################.    .=$M##M$="
echo "################H..;XM##M$=          .:+"
echo "M###################@%=           =+@MH%"
echo "@#################M/.         =+H#X%="
echo "=+M###############M,      ,/X#H+:,"
echo "  .;XM###########H=   ,/X#H+:;"
echo "     .=+HM#######M+/+HM@+=."
echo "         ,:/%XM####H/."
echo "              ,.:=-."
echo ""
echo "-----------------------------------------------"
