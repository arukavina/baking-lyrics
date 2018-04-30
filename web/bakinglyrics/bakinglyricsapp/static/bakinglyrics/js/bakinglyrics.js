
//JAVASCRIPT FUNCTIONS USED BY THE APPLICATION

//FACEBOOK LOG IN FUCTIONS
// Load the SDK asynchronously
  (function(d, s, id) {
    var js, fjs = d.getElementsByTagName(s)[0];
    if (d.getElementById(id)) return;
    js = d.createElement(s); js.id = id;
    js.src = "https://connect.facebook.net/en_US/sdk.js";
    fjs.parentNode.insertBefore(js, fjs);
  }(document, 'script', 'facebook-jssdk'));



FB.init({
        appId  : '169975227041054',
        status : false, // check login status
        cookie : true, // enable cookies to allow the server to access the session
        xfbml  : true, // parse XFBML
        channelURL : 'http://www.comehike.com/channel.html', // channel.html file
        oauth  : true, // enable OAuth 2.0
        version: 'v2.8'
      });


function checkLoginState() {
  FB.getLoginStatus(function(response) {
    statusChangeCallback(response);
  });
}

function statusChangeCallback(response) {
    if (response.status === 'connected') {

           FB.api('/me', { locale: 'en_US', fields: 'name, email' },
               function(response) {
                    console.log(response.name)
                    console.log(response.email)
                   }
                 );

    }
    else {
      // The person is not logged into your app or we are unable to tell.
     console.log("please log in")
    }
  }
///////////////////////////////////////////////////////////////////////
//GOOGLE LOG IN FUCTIONS
function onSignIn(googleUser) {
  var profile = googleUser.getBasicProfile();
  console.log('ID: ' + profile.getId()); // Do not send to your backend! Use an ID token instead.
  console.log('Name: ' + profile.getName());
  console.log('Image URL: ' + profile.getImageUrl());
  console.log('Email: ' + profile.getEmail()); // This is null if the 'email' scope is not present.
  $('#signout').show();
}

 function signOut() {
    var auth2 = gapi.auth2.getAuthInstance();
    auth2.signOut().then(function () {
      console.log('User signed out.');
    });
    $('#signout').hide();
  }
/////////////////////////////////////////////////////////


 $('#finaldiv').hide();
 $('#signout').hide();


 var selected_band_id
 var bands = [];

      $.ajax({
       type: "POST",
       url: "/get_all_bands/",
       dataType: "json",
       data: {
              csrfmiddlewaretoken: $('input[name=csrfmiddlewaretoken]').val()
              },
       success: function( data ){

              var jsonObj = jQuery.parseJSON(JSON.stringify(data));

                              for (i = 0; i < jsonObj.length; i++) {

                                                    var band_element = jsonObj[i].BandList;

                                                             var band = {band_id: band_element.band_id,
                                                                         name:band_element.name,
                                                                         decades: band_element.decades
                                                                         };

                                  bands.push(band)
                                  }

         refreshbands (bands)
         }
    });


 function getBandId (id) {

      selected_band_id = id
      var select = document.getElementById('selecteddecade');
      removeOptions(select)
      var selected_band = _.where(bands, {band_id: parseInt(id)});
      i = 1
      for (var j = 0; j < selected_band[0].decades[0].length; j ++ ) {
                 var opt = document.createElement('option');
                 opt.value = i;
                 opt.innerHTML = selected_band[0].decades[0][j];
                 select.appendChild(opt);
        i= i+1
      }
      $('.hover_bkgr_fricc').show();

    }

function removeOptions(selectbox)
    {
        var i;
        for(i=selectbox.options.length-1;i>=0;i--)
        {
            selectbox.remove(i);
        }
    }

function filterBands() {

 text = document.getElementById('inputsearchbands').value;

 if ( text.length < 1) {
     refreshbands (bands)
 }

 else if (text.length >= 1 ) {

      filteredbands = _.filter(bands, function(item) {return item.name.indexOf(text) != -1;});
      refreshbands (filteredbands)
       }

}
 $('.popupCloseButton').click(function(){
       $('.hover_bkgr_fricc').hide();
        });

 $('#finishrequest').click(function(){
                          $('.hover_bkgr_fricc').hide();
                          $('#initialdiv').hide();
                          $('#finaldiv').show();
                          $('.hover_bkgr_fricc').hide();
                          $.ajax({
                                                          type: 'POST',
                                                          url: '/send_parameters_to_server/',
                                                          dataType :"json",
                                                          async : true,
                                                          beforeSend: function() {$.blockUI({ message: '<h1><img src="http://i.stack.imgur.com/FhHRx.gif" /> Sending parameters....</h1>' }); },
                                                          complete: function() {$.unblockUI();},
                                                          data: {selected_band_id: selected_band_id,
                                                                 selected_decade: $("#selecteddecade option:selected").text(),
                                                                 csrfmiddlewaretoken: $('input[name=csrfmiddlewaretoken]').val()
                                                          },
                                                          success:function (result) {
                                                          var selected_band = _.where(bands, {band_id: parseInt(selected_band_id)});
                                                          document.getElementById("bandtitle").innerHTML = selected_band[0].name;
                                                          document.getElementById("finalpic").src="";
                                                          document.getElementById("decadeparameter").innerHTML = result['selected_decade'];
                                                          }

                          });

                          });




function refreshbands (bands) {
     if ($('#pictures').length > 0) {
     document.getElementById('pictures').innerHTML = "";
     }

     if (bands.length == 0) {
     document.getElementById('pictures').innerHTML = "<h2>No results</h2>";

     }
     else {
                html = ""
                for(var i = 0; i < bands.length; i++) {

                            if (i == 0) {
                            html += '<div class="row" id="rowdiv" style= "margin-bottom:30px;">'
                             }

                            html += '<div class="col-xs-4"  style="height:100px; width:250px;">'
                            html +="<h2>" + bands[i].name + "  </h2>"
                            html += "<button id = "+ bands[i].band_id + " type='button' onclick=getBandId(this.id) class='btn btn-primary'>Choose!</button>"

                            html +="</div>"

                            if ((i+1)   % 4 == 0)  {

                            html +='</div><div class="row" id="rowdiv" style= "margin-bottom:30px;">'
                            }
                            if (i==bands.length) {
                            html +="</div>"
                            }
                }
                 if ($('#pictures').length > 0) {
                 document.getElementById('pictures').innerHTML = html
                  }
       }
}

function back() {

      refreshbands(bands)
      $('#finaldiv').hide();
      document.getElementById('inputsearchbands').value = "";
      $('#initialdiv').show();
}
