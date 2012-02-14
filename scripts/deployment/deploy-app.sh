#!/bin/bash
#
# Deploy application to the cloud.
# Assumes a lot of things - please test with a staging system
#

set -e

#
# Repository settings
#
repo_url='ssh://hg@one.synovel.pvt/social'
repo_revision='default'


#
# List of stylesheets and scripts that need bundling
#
social_css='rsrcs/css/social.css:rsrcs/css/messaging.css:'\
'rsrcs/css/jquery.ui.css:rsrcs/css/widgets.css:rsrcs/css/screen-size.css:'\
'rsrcs/css/jquery.tagedit.css'

about_css='rsrcs/css/static.css'

jquery_js='rsrcs/js/jquery-1.6.4.js:rsrcs/js/jquery.address-1.4.js:'\
'rsrcs/js/jquery.autogrow-textarea.js:rsrcs/js/jquery.html5form-1.3.js:'\
'rsrcs/js/jquery.iframe-transport.js:rsrcs/js/jquery.ui.js:'\
'rsrcs/js/jquery.ui.menu.js:rsrcs/js/jquery.ui.autocomplete.js:'\
'rsrcs/js/jquery.autoGrowInput.js:rsrcs/js/jquery.tagedit.js:'\
'rsrcs/js/jquery.cookie.js'

social_js='rsrcs/js/social.js'

comet_js='rsrcs/js/json2.js:rsrcs/js/Cometd.js:rsrcs/js/ReloadExtension.js:'\
'rsrcs/js/jquery.cometd.js:rsrcs/js/jquery.cometd-reload.js'


#
# Output files
#
out_styles=( "$social_css" "$about_css" )
out_scripts=( "$jquery_js" "$social_js" "$comet_js" )


#
# Images folder
#
img_dir='rsrcs/img'


#
# Deployment environment configuration
#
app_hosts=('app-1.flocked.in' 'app-2.flocked.in')
cdn_host='https://depmigrvpjbd.cloudfront.net'


#
# Other configurations
#
yui_compressor='/opt/yuicompressor-2.4.6/build/yuicompressor-2.4.6.jar'


#
####################  END OF CONFIGURATION ###################
#

set -x
cur_dir=`pwd`
tmp_dir=`mktemp -d -t social.XXXXXX`

src=$tmp_dir/src
static=$tmp_dir/static
public=$src/public
mkdir $static


function cleanup() {
  rm -rf $tmp_dir
}
trap cleanup 0

function error() {
  local PARENT_LINENO="$1"
  local MESSAGE="$2"
  local CODE="${3:-1}"
  if [[ -n "$MESSAGE" ]] ; then
    echo "Error at line ${PARENT_LINENO}: ${MESSAGE}; exiting with status ${CODE}"
  else
    echo "Error at line ${PARENT_LINENO}; exiting with status ${CODE}"
  fi
  exit "${CODE}"
}
trap 'error ${LINENO}' ERR

#
# Fetch files from the repository.
# Don't use stale files from the current checkout.
#
hg clone $repo_url $src && cd $src && hg update -r $repo_revision


#
# Process images - copy them and replace all references to
# the image with an absolute url (over CDN)
#
img_dir=$public/$img_dir
for img in `ls -1 $img_dir`; do
  checksum=`md5sum $img_dir/$img | cut -f1 -d' '`
  filename=$checksum.${img##*.}
  cp $img_dir/$img $static/$filename

  find $src/templates $src/social $public/rsrcs/js $public/rsrcs/css $public/about $public/*.html -type f \
        | xargs sed -i "s=/rsrcs/img/$img=$cdn_host/static/$filename="
done


#
# Process stylesheets and scripts.
# Bundles them to fewer files and replace references in templates and application.
#
function _bundle() {
  outfile=$1
  ext=$2

  files=`echo $outfile | sed 's/:/ /g'`
  (
    for file in ${files[*]}; do
      java -jar $yui_compressor $public/$file
    done
  ) > $tmp_dir/compressed.$ext

  if [ -f $tmp_dir/compressed.$ext ]; then
    checksum=`md5sum $tmp_dir/compressed.$ext | cut -f1 -d' '`
    mv $tmp_dir/compressed.$ext $static/$checksum.$ext

    # File paths have '/' in them, escape them for regex matching
    paths_escaped=`echo $outfile | sed -e 's/\\(\\.\\|\\/\\|\\*\\|\\[\\|\\]\\|\\\\\\)/\\\\&/g'`
    match_expr=`echo $paths_escaped | sed 's/:/\|/g'`

    find $src/templates $src/social $public/about $public/*.html -type f | while read name; do
      awk_output=$tmp_dir/`basename $name`.awk
      awk "!/($match_expr)/ { print \$0 };
            /($match_expr)/ && !done {
              gsub(/\/($match_expr)/, \"$cdn_host/static/$checksum.$ext\");
              print \$0;
              done=1
            };" $name > $awk_output
      mv $awk_output $name
    done
  fi
  rm -f $tmp_dir/compressed.$ext
}

# Process stylesheets
for outfile in ${out_styles[*]}; do
  _bundle $outfile "css"
done

# Process scripts
for outfile in ${out_scripts[*]}; do
  _bundle $outfile "js"
done

# Create a version file.
cd $src
hg identify -r $repo_revision > $src/VERSION

# Remove mercurial data from src folder
rm -rf $src/.hg

# Decrypt configuration file and copy it to the right path
# and create a tarball of source and static files.
cd $tmp_dir
$src/scripts/deployment/encrypt-files.sh decrypt \
    $src/scripts/deployment/files.tbz.asc && mv files/production.cfg $src/etc/
if [ ! -f $src/etc/production.cfg ]; then
  echo "Config file not found.  Entered wrong password?"
  exit -1
fi

tar -cvjf upload.tar.bz2 static src

# Copy static files and the modified src to application servers
for remote in ${app_hosts[*]}; do
  scp upload.tar.bz2 social@$remote:
  ssh social@$remote "tar -xjf upload.tar.bz2; src/scripts/deployment/update-social.sh"
done

cd $cur_dir
