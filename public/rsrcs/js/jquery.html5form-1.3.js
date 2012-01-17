/*
 *  Html5 Form Plugin - jQuery plugin
 *  HTML5 form Validation form Internet Explorer & Firefox
 *  Version 1.2  / English
 *  
 *  written by Matias Mancini http://www.matiasmancini.com.ar
 * 
 *  Copyright (c) 2010 Matias Mancini (http://www.matiasmancini.com.ar)
 *  Dual licensed under the MIT (MIT-LICENSE.txt)
 *  and GPL (GPL-LICENSE.txt) licenses.
 *
 *  Built for jQuery library
 *	http://jquery.com
 *
 */
(function($){
    $.fn.html5form = function(options){
        
        $(this).each(function(){
            
            //default configuration properties
            var defaults = {
                method : $(this).attr('method'), 
                labels : 'show',
                colorOn : '#000000', 
                colorOff : '#a1a1a1', 
                action : $(this).attr('action'),
                messages : false,
                emptyMessage : false,
                emailMessage : false,
                allBrowsers : false 
            };   
            var opts = $.extend({}, defaults, options);
            
            //Filters latest WebKit versions & Firefox 4 
            if(!opts.allBrowsers){
                //exit if webkit +533
                if($.browser.webkit && parseInt($.browser.version)>=533){
                    return false;
                }
                //exit if firefox 4
                if($.browser.mozilla && parseInt($.browser.version)>=2){
                    return false;   
                }   
            }
                        
            //Private properties
            var form = $(this);
            var required = new Array();
            var email = new Array();

            //Setup color & placeholder function
            function fillInput(input){
                if(input.attr('placeholder') && input.attr('type')!='password'){
                    input.val(input.attr('placeholder'));
                    input.css('color', opts.colorOff);
                    if($.browser.mozilla){
                        input.css('-moz-box-shadow', 'none');   
                    }
                }else{
                    if(!input.data('value')){
                        if(input.val()!=''){
                            input.data('value', input.val());   
                        }
                    }else{
                        input.val(input.data('value'));
                    }   
                    input.css('color', opts.colorOn);
                }
            }

            form.bind('restorePlaceHolders', function () {
                $.each($(':input:not(:button, :submit, :radio, :checkbox, select)', form), function() {
                    input = $(this);
                    if (input.val() == '')
                        fillInput(input);
                });
            });
            
            //Label hiding (if required)
            if(opts.labels=='hide'){
                $(this).find('label').hide();   
            }
            
            //Select event handler (just colors)
            $.each($('select', this), function(){
                $(this).css('color', opts.colorOff);
                $(this).change(function(){
                    $(this).css('color', opts.colorOn);
                });
            });
                        
            //For each textarea & visible input excluding button, submit, radio, checkbox and select
            $.each($(':input:not(:button, :submit, :radio, :checkbox, select)', form), function(i) {
                
                //Setting color & placeholder
                fillInput($(this));
                
                //Make array of required inputs
                if(this.getAttribute('required')!=null){
                    required[i]=$(this);
                }
                
                //Make array of Email inputs               
                if(this.getAttribute('type')=='email'){
                    email[i]=$(this);
                }
                          
                //FOCUS event attach 
                //If input value == placeholder attribute will clear the field
                //If input type == url will not
                //In both cases will change the color with colorOn property                 
                $(this).bind('focus', function(ev){
                    ev.preventDefault();
                    if(this.value == $(this).attr('placeholder')){
                        if(this.getAttribute('type')!='url'){
                            $(this).attr('value', '');   
                        } 
                    }
                    $(this).css('color', opts.colorOn);
                });
                
                //BLUR event attach
                //If input value == empty calls fillInput fn
                //if input type == url and value == placeholder attribute calls fn too
                $(this).bind('blur', function(ev){
                    ev.preventDefault();
                    if(this.value == ''){
                        fillInput($(this));
                    }
                    else{
                        if((this.getAttribute('type')=='url') && ($(this).val()==$(this).attr('placeholder'))){
                            fillInput($(this));
                        }
                    }
                });
                
                //Limits content typing to TEXTAREA type fields according to attribute maxlength
                $('textarea').filter(this).each(function(){
                    if($(this).attr('maxlength')>0){
                        $(this).keypress(function(ev){
                            var cc = ev.charCode || ev.keyCode;
                            if(cc == 37 || cc == 39) {
                                return true;
                            }
                            if(cc == 8 || cc == 46) {
                                return true;
                            }
                            if(this.value.length >= $(this).attr('maxlength')){
                                return false;   
                            }
                            else{
                                return true;
                            }
                        });
                    }
                });
            });

            if (form.data('html5form'))
                return;
            form.data('html5form', true);

            form.bind('html5formvalidate', function(ev) {
                var emptyInput=null;
                var emailError=null;
                var input = $(':input:not(:button, :submit, :radio, :checkbox, select)', form);                    
                
                // Re-create required elements list
                required.length=0;
                $(input).each(function(i){
                    if(this.getAttribute('required')!=null)
                        required[i]=$(this);
                });

                //Search for empty fields & value same as placeholder
                //returns first input founded
                //Add messages for multiple languages
                $(required).each(function(key, value) {
                    if(value==undefined){
                        return true;
                    }
                    var title = $(this).attr('title') || $(this).attr('name')
                    if(($(this).val()==$(this).attr('placeholder')) || ($(this).val()=='')){
                        emptyInput=$(this);
                        if(opts.emptyMessage){
                            //Customized empty message
                            $$.alerts.error(opts.emptyMessage);
                        }
                        else if(opts.messages=='es'){
                            //Spanish empty message
                            $$.alerts.error('El campo '+title+' es requerido.');
                        }
                        else if(opts.messages=='en'){
                            //English empty message
                            $$.alerts.error('The '+title+' field is required.');
                        }
                        else if(opts.messages=='it'){
                            //Italian empty message
                            $$.alerts.error('Il campo '+title+' é richiesto.');
                        }
                        else if(opts.messages=='de'){
                            //German empty message
                            $$.alerts.error(title+' ist ein Pflichtfeld.');
                        }
                        else if(opts.messages=='fr'){
                            //Frech empty message
                            $$.alerts.error('Le champ '+title+' est requis.');
                        }
                        else if(opts.messages=='nl' || opts.messages=='be'){
                            //Dutch messages
                            $$.alerts.error(title+' is een verplicht veld.');
                        }                     
                        return false;
                    }
                return emptyInput;
                });
                    
                //check email type inputs with regular expression
                //return first input founded
                $(email).each(function(key, value) {
                    if(value==undefined){
                        return true;
                    }
                    if($(this).val().search(/^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/i)){
                        emailError=$(this);
                        return false;
                    }
                return emailError;
                });
                
                //Submit form ONLY if emptyInput & emailError are null
                if(!emptyInput && !emailError){
                    
                    //Clear all empty value fields before Submit 
                    $(input).each(function(){
                        if($(this).val()==$(this).attr('placeholder')){
                            $(this).val('');
                        }
                    }); 

                    return true;

                }else{
                    if(emptyInput){
                        $(emptyInput).focus().select();              
                    }
                    else if(emailError){
                        //Customized email error messages (Spanish, English, Italian, German, French, Dutch)
                        if(opts.emailMessage){
                            $$.alerts.error(opts.emailMessage);
                        }
                        else if(opts.messages=='es'){
                            $$.alerts.error('Ingrese una direcci&oacute;n de correo v&aacute;lida por favor.');
                        }
                        else if(opts.messages=='en'){
                            $$.alerts.error('Please type a valid email address.');
                        }
                        else if(opts.messages=='it'){
                            $$.alerts.error("L'indirizzo e-mail non &eacute; valido.");
                        }
                        else if(opts.messages=='de'){
                            $$.alerts.error("Bitte eine g&uuml;ltige E-Mail-Adresse eintragen.");
                        }
                        else if(opts.messages=='fr'){
                            $$.alerts.error("Entrez une adresse email valide s&rsquo;il vous plait.");
                        }
                        else if(opts.messages=='nl' || opts.messages=='be'){
                            $$.alerts.error('Voert u alstublieft een geldig email adres in.');
                        }
                        $(emailError).select();
                    }else{
                        alert('Unknown Error');                        
                    }
                }
                ev.preventDefault();
                return false;
            });
        });
    } 
})(jQuery);
