#!/bin/bash
#
# Deploy application to the cloud.
# Assumes a lot of things - please test with a staging system
#

set -x

#
# Repository settings
#
repo_url='/home/tux/social'
repo_revision='tip'


#
# List of stylesheets and scripts that need bundling
#
social_css='rsrcs/css/social.css:rsrcs/css/messaging.css:'\
'rsrcs/css/jquery.ui.css:rsrcs/css/widgets.css'

about_css='rsrcs/css/about.css'

jquery_js='rsrcs/js/jquery-1.6.3.js:rsrcs/js/jquery.address-1.4.js:'\
'rsrcs/js/jquery.autogrow-textarea.js:rsrcs/js/jquery.html5form-1.3.js:'\
'rsrcs/js/jquery.iframe-transport.js:rsrcs/js/jquery.ui.js:'\
'rsrcs/js/jquery.ui.menu.js:rsrcs/js/jquery.ui.autocomplete.js'

social_js='rsrcs/js/social.js'


#
# Output files
#
out_styles=( "$social_css" "$about_css" )
out_scripts=( "$jquery_js" "$social_js" )


#
# Images folder
#
img_dir='rsrcs/img'


#
# Deployment environment configuration
#
app_hosts=('app-2.flocked.in')
cdn_host='https://doy9z51iqd595.cloudfront.net'


#
# Other configurations
#
yui_compressor='/opt/yuicompressor-2.4.6/build/yuicompressor-2.4.6.jar'


#
####################  END OF CONFIGURATION ###################
#

cur_dir=`pwd`
tmp_dir=`mktemp -d`

source=$tmp_dir/source
static=$tmp_dir/static
public=$source/public
mkdir $static


function cleanup() {
  rm -rf $tmp_dir
}

function error_exit() {
  echo "ERROR ABORT: $*"
  cleanup
  exit -1
}


#
# Fetch files from the repository.
# Don't use stale files from the current checkout.
#
(hg clone $repo_url $source && cd $source && hg update -r $repo_revision) || error_exit "Could not clone the repository"


#
# Process images - copy them and replace all references to
# the image with an absolute url (over CDN)
#
img_dir=$public/$img_dir
for img in `ls -1 $img_dir`; do
  checksum=`md5sum $img_dir/$img | cut -f1 -d' '`
  filename=$checksum.${img##*.}
  cp $img_dir/$img $static/$filename

  find $source/templates $source/social $public/rsrcs/js $public/rsrcs/css -type f \
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
      java -jar $yui_compressor $public/$file || error_exit "An error occurred while processing $file";
    done
  ) > $tmp_dir/compressed.$ext || error_exit "An error occurred while processing stylesheets"

  if [ -f $tmp_dir/compressed.$ext ]; then
    checksum=`md5sum $tmp_dir/compressed.$ext | cut -f1 -d' '`
    mv $tmp_dir/compressed.$ext $static/$checksum.$ext

    # File paths have '/' in them, escape them for regex matching
    paths_escaped=`echo $outfile | sed -e 's/\\(\\.\\|\\/\\|\\*\\|\\[\\|\\]\\|\\\\\\)/\\\\&/g'`
    match_expr=`echo $paths_escaped | sed 's/:/\|/g'`

    find $source/templates $source/social -type f | while read name; do
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

# Remove mercurial data from source folder
rm -rf $source/.hg

# Copy static files and the modified source to application servers
for remote in ${app_hosts[*]}; do
  scp -r $static social@$remote:
  scp -r $source social@$remote:
  ssh social@$remote "source/scripts/deployment/update-social.sh"
done

cd $cur_dir
cleanup
