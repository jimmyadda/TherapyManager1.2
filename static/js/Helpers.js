
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    const Lang = urlParams.get('lang')

    function translate_DOM_element(cssclass,jsonobj,fromlanguage,tolanguage){
        tolanguage = tolanguage || "EN";
        const translate_Json= jsonobj
        const from_lang = fromlanguage;
        const to_lang = tolanguage; 
        console.log(translate_Json)

        $('.'+cssclass).each(function(i, obj) {
            //search in JSON by key & lang
            var obj_text = $(obj).text()
            var obj_key = $(obj).attr('key');     
            var objType = $(obj).get(0).tagName; //if INPUT change val() not text()


            var translated_text  = translate_Json[tolanguage][obj_key]
            if(translated_text){
            $(obj).text(translated_text);
            if(objType=="INPUT"){$(obj).val(translated_text);}
            }
            

            //Load css for to lang        
            $(obj).removeClass(fromlanguage);
            $(obj).addClass(tolanguage);
            
        });
    
        if(tolanguage == "HE"){
        $("body").css("direction","rtl");
        $("body").css("text-align","right");
        $('#pullcss').removeClass('pull-right').addClass('pull-left');    
        $('#pullcss1').removeClass('pull-right').addClass('pull-left');     
        }
        else{
            $("body").css("direction","ltr");
            $("body").css("text-align","left");
            $('#pullcss').removeClass('pull-left').addClass('pull-right');
            $('#pullcss1').removeClass('pull-left').addClass('pull-right');

            }
    }



