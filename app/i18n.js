(() => {
  'use strict';
  const words = {
    'My Farm':['मेरा खेत','माझे शेत'], 'Advisory log':['सलाह सूची','सल्ला नोंद'],
    'Crop recommendation':['फसल सुझाव','पीक शिफारस'], 'Leaf scanner':['पत्ती स्कैनर','पान स्कॅनर'],
    'Crop health scanner':['फसल स्वास्थ्य स्कैनर','पीक आरोग्य स्कॅनर'],
    'Farm history':['खेत का इतिहास','शेताचा इतिहास'], 'Assistant':['सहायक','सहाय्यक'],
    'Farmer view':['किसान दृश्य','शेतकरी दृश्य'], 'Analyst view':['विश्लेषक दृश्य','विश्लेषक दृश्य'],
    'Log out':['लॉग आउट','लॉग आउट'], 'Viewing farm':['चुना हुआ खेत','निवडलेले शेत'],
    'Farm record':['खेत रिकॉर्ड','शेत नोंद'], 'Refresh':['रीफ्रेश करें','रीफ्रेश करा'],
    'Your farm profile and measurements saved to your account':['आपकी खेत प्रोफ़ाइल और माप आपके खाते में सहेजे गए हैं','तुमची शेत प्रोफाइल आणि मोजमाप खात्यात जतन केले आहेत'],
    'Farm profile':['खेत प्रोफ़ाइल','शेत प्रोफाइल'], 'Current crop and saved readings':['वर्तमान फसल और सहेजे गए माप','सध्याचे पीक आणि जतन केलेली मोजमापे'],
    'Edit farm profile':['खेत प्रोफ़ाइल संपादित करें','शेत प्रोफाइल संपादित करा'],
    'Save farm profile':['खेत प्रोफ़ाइल सहेजें','शेत प्रोफाइल जतन करा'],
    'Get farm advisory':['खेत की सलाह लें','शेत सल्ला मिळवा'],
    'Uses this farm’s saved context and model results.':['इस खेत के सहेजे गए विवरण और मॉडल परिणामों का उपयोग करता है।','या शेताची जतन केलेली माहिती आणि मॉडेल निकाल वापरतो.'],
    'Crop recommendation':['फसल सुझाव','पीक शिफारस'],
    'Precise soil-based guidance needs values from your soil test. AgriPilot will not fill in missing soil values.':['सटीक मिट्टी-आधारित सलाह के लिए मिट्टी परीक्षण के मान चाहिए। AgriPilot अनुपलब्ध मान नहीं भरेगा।','अचूक माती-आधारित मार्गदर्शनासाठी माती परीक्षणातील मूल्ये आवश्यक आहेत. AgriPilot नसलेली मूल्ये भरणार नाही.'],
    'Farm inputs':['खेत के इनपुट','शेताची माहिती'],
    'Do you have a soil test report?':['क्या आपके पास मिट्टी परीक्षण रिपोर्ट है?','तुमच्याकडे माती परीक्षण अहवाल आहे का?'],
    'Yes, I have the report and will confirm its values':['हाँ, रिपोर्ट है और मैं उसके मानों की पुष्टि करूंगा','होय, अहवाल आहे आणि मी त्यातील मूल्ये निश्चित करेन'],
    'No':['नहीं','नाही'], 'Nitrogen (N), kg/ha':['नाइट्रोजन (N), किग्रा/हेक्टेयर','नायट्रोजन (N), किलो/हेक्टर'],
    'Phosphorus (P), kg/ha':['फॉस्फोरस (P), किग्रा/हेक्टेयर','फॉस्फरस (P), किलो/हेक्टर'],
    'Potassium (K), kg/ha':['पोटैशियम (K), किग्रा/हेक्टेयर','पोटॅशियम (K), किलो/हेक्टर'],
    'Soil pH':['मिट्टी का pH','मातीचा pH'], 'Temperature °C':['तापमान °C','तापमान °C'],
    'Humidity %':['आर्द्रता %','आर्द्रता %'], 'Rainfall mm':['वर्षा मिमी','पाऊस मिमी'],
    'Get model recommendation':['मॉडल से फसल सुझाव लें','मॉडेलकडून पीक शिफारस घ्या'],
    'Upload a clear leaf image for the saved Step 3 classifier. Results and the Grad-CAM overlay come from the model response.':['सहेजे गए Step 3 वर्गीकारक के लिए पत्ती की स्पष्ट तस्वीर अपलोड करें। परिणाम और Grad-CAM मॉडल से आते हैं।','जतन केलेल्या Step 3 वर्गीकारकासाठी पानाचा स्पष्ट फोटो अपलोड करा. निकाल आणि Grad-CAM मॉडेलकडून मिळतात.'],
    'Crop shown in the image':['तस्वीर में दिखाई गई फसल','फोटोतील पीक'],
    'Select or enter crop name':['फसल चुनें या नाम लिखें','पीक निवडा किंवा नाव लिहा'],
    'Leaf image (JPG, PNG, WebP; up to 10 MB)':['पत्ती की तस्वीर (JPG, PNG, WebP; अधिकतम 10 MB)','पानाचा फोटो (JPG, PNG, WebP; कमाल 10 MB)'],
    'Analyze leaf':['पत्ती की जांच करें','पानाचे विश्लेषण करा'],
    'Saved farm history':['खेत का सहेजा इतिहास','शेताचा जतन केलेला इतिहास'],
    'Records below are fetched from the selected farm’s database history endpoints.':['नीचे के रिकॉर्ड चुने गए खेत के डेटाबेस इतिहास से लिए गए हैं।','खालील नोंदी निवडलेल्या शेताच्या डेटाबेस इतिहासातून घेतल्या आहेत.'],
    'Recent predictions and advisories':['हाल के अनुमान और सलाह','अलीकडील अंदाज आणि सल्ले'],
    'Refresh history':['इतिहास रीफ्रेश करें','इतिहास रीफ्रेश करा'],
    'Response language':['जवाब की भाषा','उत्तराची भाषा'], 'Farm assistant':['खेत सहायक','शेत सहाय्यक'],
    'Send':['भेजें','पाठवा'], 'Select a database farm to load history.':['इतिहास लोड करने के लिए डेटाबेस में खेत चुनें।','इतिहास लोड करण्यासाठी डेटाबेसमधील शेत निवडा.'],
    'Loading live weather…':['लाइव मौसम लोड हो रहा है…','थेट हवामान लोड होत आहे…'],
    'Loading saved history…':['सहेजा इतिहास लोड हो रहा है…','जतन केलेला इतिहास लोड होत आहे…'],
    'No saved prediction, advisory, or assistant history for this farm yet.':['इस खेत के लिए अभी कोई अनुमान, सलाह या सहायक इतिहास सहेजा नहीं गया है।','या शेतासाठी अजून अंदाज, सल्ला किंवा सहाय्यक इतिहास जतन केलेला नाही.'],
    'No saved prediction, advisory, or assistant history for this farm yet.':['इस खेत के लिए अभी कोई अनुमान, सलाह या सहायक इतिहास सहेजा नहीं गया है।','या शेतासाठी अजून अंदाज, सल्ला किंवा सहाय्यक इतिहास जतन केलेला नाही.'],
    'No crop recommendation yet.':['अभी कोई फसल सुझाव नहीं।','अजून पीक शिफारस नाही.'],
    'No crop-health scans yet.':['अभी कोई फसल स्वास्थ्य स्कैन नहीं।','अजून पीक आरोग्य स्कॅन नाही.'],
    'No history yet.':['अभी कोई इतिहास नहीं।','अजून इतिहास नाही.'],
    'Weather data is currently unavailable.':['मौसम की जानकारी अभी उपलब्ध नहीं है।','हवामानाची माहिती सध्या उपलब्ध नाही.'],
    'Unable to identify reliably.':['विश्वसनीय पहचान नहीं हो सकी।','विश्वसनीय ओळख पटली नाही.'],
    'Please upload a clearer crop image.':['कृपया फसल की अधिक स्पष्ट तस्वीर अपलोड करें।','कृपया पिकाचा अधिक स्पष्ट फोटो अपलोड करा.'],
    'Choose a leaf image first.':['पहले पत्ती की तस्वीर चुनें।','आधी पानाचा फोटो निवडा.'],
    'Select or enter the crop shown in the image.':['तस्वीर में दिखाई गई फसल चुनें या लिखें।','फोटोतील पीक निवडा किंवा लिहा.'],
    'Upload a JPEG, PNG, or WebP image.':['JPEG, PNG या WebP तस्वीर अपलोड करें।','JPEG, PNG किंवा WebP फोटो अपलोड करा.'],
    'Get advisory':['सलाह लें','सल्ला घ्या'], 'Loading saved farm data…':['सहेजे खेत का डेटा लोड हो रहा है…','जतन केलेली शेत माहिती लोड होत आहे…'],
    'Connecting to local AgriPilot API…':['स्थानीय AgriPilot API से जुड़ रहा है…','स्थानिक AgriPilot API शी जोडत आहे…'],
    'No verified soil-test values loaded.':['मिट्टी परीक्षण के सत्यापित मान लोड नहीं हुए।','माती परीक्षणाची पडताळलेली मूल्ये लोड झालेली नाहीत.'],
    'No farmer-confirmed soil report or sourced weather measurement is saved. Seed/demo readings are not prefilled.':['किसान द्वारा पुष्टि की गई मिट्टी रिपोर्ट या स्रोत सहित मौसम माप सहेजा नहीं गया है। नमूना रीडिंग पहले से नहीं भरी जातीं।','शेतकऱ्याने निश्चित केलेला माती अहवाल किंवा स्रोतासह हवामान मोजमाप जतन केलेले नाही. नमुना मोजमापे आधी भरलेली नसतात.'],
    'The server is unavailable.':['सर्वर उपलब्ध नहीं है।','सर्व्हर उपलब्ध नाही.'],
    'Today':['आज','आज'], 'ML insights':['एमएल जानकारी','एमएल माहिती'],
    'No verified soil-test values loaded.':['मिट्टी परीक्षण के सत्यापित मान लोड नहीं हुए।','माती परीक्षणाची पडताळलेली मूल्ये लोड झालेली नाहीत.'],
    'Farm':['खेत','शेत'], 'Owner':['मालिक','मालक'], 'Location':['स्थान','ठिकाण'], 'Area':['क्षेत्रफल','क्षेत्रफळ'],
    'Soil':['मिट्टी','माती'], 'Irrigation':['सिंचाई','सिंचन'], 'Crop':['फसल','पीक'], 'Variety':['किस्म','जात'], 'Season':['मौसम','हंगाम'],
    'Temperature':['तापमान','तापमान'], 'Humidity':['आर्द्रता','आर्द्रता'], 'Recorded rainfall':['दर्ज वर्षा','नोंदलेला पाऊस'],
    'Soil moisture':['मिट्टी की नमी','मातीतील ओलावा'], 'Measurement saved':['माप सहेजा गया','मोजमाप जतन केले'],
    'Unavailable':['उपलब्ध नहीं','उपलब्ध नाही'], 'Not recorded':['दर्ज नहीं','नोंदलेले नाही'], 'No measurement':['कोई माप नहीं','मोजमाप नाही'],
    'Live weather':['लाइव मौसम','थेट हवामान'], 'Farm name':['खेत का नाम','शेताचे नाव'], 'Current crop':['वर्तमान फसल','सध्याचे पीक'],
    'Save farm profile':['खेत प्रोफ़ाइल सहेजें','शेत प्रोफाइल जतन करा'], 'Get farm advisory':['खेत की सलाह लें','शेत सल्ला मिळवा'],
    'Crop classifier':['फसल वर्गीकारक','पीक वर्गीकारक'], 'Leaf diagnosis':['पत्ती निदान','पानाचे निदान'],
    'Farm advisory':['खेत की सलाह','शेत सल्ला'], 'Assistant query':['सहायक प्रश्न','सहाय्यक प्रश्न'],
    'Irrigation':['सिंचाई','सिंचन'], 'Please say whether you have a soil test report.':['बताएं कि आपके पास मिट्टी परीक्षण रिपोर्ट है या नहीं।','माती परीक्षण अहवाल आहे की नाही ते सांगा.'],
    'Precise soil-based crop recommendation requires soil information from a soil test report.':['सटीक मिट्टी-आधारित फसल सुझाव के लिए मिट्टी परीक्षण रिपोर्ट के मान आवश्यक हैं।','अचूक माती-आधारित पीक शिफारशीसाठी माती परीक्षण अहवालातील मूल्ये आवश्यक आहेत.'],
    'Enter a valid number for every required input.':['हर आवश्यक फ़ील्ड में मान्य संख्या दर्ज करें।','प्रत्येक आवश्यक फील्डमध्ये वैध संख्या भरा.'],
    'Check the input ranges for pH and rainfall.':['pH और वर्षा के मान जांचें।','pH आणि पावसाची मूल्ये तपासा.'],
    'Choose a leaf image first.':['पहले पत्ती की तस्वीर चुनें।','आधी पानाचा फोटो निवडा.'],
    'Select or enter the crop shown in the image.':['तस्वीर में दिखाई गई फसल चुनें या लिखें।','फोटोतील पीक निवडा किंवा लिहा.'],
    'Upload a JPEG, PNG, or WebP image.':['JPEG, PNG या WebP तस्वीर अपलोड करें।','JPEG, PNG किंवा WebP फोटो अपलोड करा.'],
    'No farm records are available.':['खेत का कोई रिकॉर्ड उपलब्ध नहीं है।','शेताच्या नोंदी उपलब्ध नाहीत.'],
    'Select a saved farm first.':['पहले सहेजा हुआ खेत चुनें।','आधी जतन केलेले शेत निवडा.'],
    'Get farm advisory':['खेत की सलाह लें','शेत सल्ला मिळवा'], 'Farm request failed':['खेत अनुरोध विफल हुआ','शेत विनंती अयशस्वी झाली'],
    'Could not save farm details.':['खेत का विवरण सहेजा नहीं जा सका।','शेताची माहिती जतन करता आली नाही.'],
    'Saving farm details…':['खेत का विवरण सहेजा जा रहा है…','शेताची माहिती जतन होत आहे…']
    ,'Farm record':['खेत रिकॉर्ड','शेत नोंद'], 'Current crop and saved readings':['वर्तमान फसल और सहेजे गए माप','सध्याचे पीक आणि जतन केलेली मोजमापे'],
    'The values above are stored farm measurements, not live weather.':['ऊपर दिए गए मान खेत में दर्ज माप हैं, लाइव मौसम नहीं।','वरील मूल्ये शेतातील नोंदवलेली मोजमापे आहेत, थेट हवामान नाही.'],
    'Area (hectares)':['क्षेत्रफल (हेक्टेयर)','क्षेत्रफळ (हेक्टर)'], 'Irrigation system':['सिंचाई प्रणाली','सिंचन व्यवस्था'],
    'Sowing date':['बुवाई की तारीख','पेरणीची तारीख'], 'Uses this farm’s saved context and model results.':['यह इस खेत की सहेजी जानकारी और मॉडल परिणामों का उपयोग करता है।','हे या शेताची जतन केलेली माहिती आणि मॉडेल निकाल वापरते.'],
    'Model':['मॉडल','मॉडेल'], 'Confidence':['विश्वास स्तर','विश्वास पातळी'],
    'Model recommendation:':['मॉडल की फसल सलाह:','मॉडेलची पीक शिफारस:'],
    'Alternative predictions':['वैकल्पिक अनुमान','पर्यायी अंदाज'], 'Model explanation':['मॉडल का स्पष्टीकरण','मॉडेलचे स्पष्टीकरण'],
    'Leaf analysis result':['पत्ती विश्लेषण परिणाम','पान विश्लेषण निकाल'], 'Grad-CAM model explanation':['Grad-CAM मॉडल स्पष्टीकरण','Grad-CAM मॉडेल स्पष्टीकरण'],
    'Other model candidates':['मॉडल के अन्य विकल्प','मॉडेलचे इतर पर्याय'], 'Symptoms':['लक्षण','लक्षणे'],
    'Precautions':['सावधानियां','काळजी'], 'General management':['सामान्य प्रबंधन','सामान्य व्यवस्थापन'],
    'Prevention':['रोकथाम','प्रतिबंध'], 'Severity':['गंभीरता','तीव्रता'], 'Diagnosis':['निदान','निदान'],
    'Healthy classification':['स्वस्थ वर्गीकरण','निरोगी वर्गीकरण'], 'Yes':['हाँ','होय'],
    'Relative humidity':['सापेक्ष आर्द्रता','सापेक्ष आर्द्रता'], 'Recent precipitation':['हाल की वर्षा','अलीकडील पर्जन्य'],
    'Daily forecast:':['दैनिक पूर्वानुमान:','दैनिक अंदाज:'], 'Supported crops in the saved model:':['सहेजे गए मॉडल में समर्थित फसलें:','जतन केलेल्या मॉडेलमधील समर्थित पिके:'],
    'Other crops are rejected.':['अन्य फसलें स्वीकार नहीं की जातीं।','इतर पिके नाकारली जातात.'],
    'Crop coverage is unavailable from the model metadata.':['मॉडल जानकारी से फसल समर्थन उपलब्ध नहीं है।','मॉडेल माहितीमध्ये पीक समर्थन उपलब्ध नाही.'],
    'Please say whether you have a soil test report.':['बताएं कि आपके पास मिट्टी परीक्षण रिपोर्ट है या नहीं।','माती परीक्षण अहवाल आहे की नाही ते सांगा.'],
    'Enter a valid number for every required input.':['हर आवश्यक फ़ील्ड में मान्य संख्या दर्ज करें।','प्रत्येक आवश्यक फील्डमध्ये वैध संख्या भरा.'],
    'Image is larger than 10 MB. Choose a smaller image.':['तस्वीर 10 MB से बड़ी है। छोटी तस्वीर चुनें।','फोटो 10 MB पेक्षा मोठा आहे. लहान फोटो निवडा.'],
    'Select or enter the crop shown in the image.':['तस्वीर में दिखाई गई फसल चुनें या लिखें।','फोटोतील पीक निवडा किंवा लिहा.'],
    'Diagnosis returned by the saved Step 3 model.':['सहेजे गए Step 3 मॉडल से निदान मिला।','जतन केलेल्या Step 3 मॉडेलकडून निदान मिळाले.'],
    'Prediction returned by the saved Step 2 model.':['सहेजे गए Step 2 मॉडल से अनुमान मिला।','जतन केलेल्या Step 2 मॉडेलकडून अंदाज मिळाला.']
    ,'Log out':['लॉग आउट','लॉग आउट'], 'Farm decision assistant':['खेत निर्णय सहायक','शेती निर्णय सहाय्यक'],
    'Nitrogen (N)':['नाइट्रोजन (N)','नायट्रोजन (N)'], 'Phosphorus (P)':['फॉस्फोरस (P)','फॉस्फरस (P)'],
    'Potassium (K)':['पोटैशियम (K)','पोटॅशियम (K)'], 'Variety':['किस्म','जात'], 'Season':['मौसम','हंगाम'],
    'The farm location could not be matched to the saved state.':['खेत के स्थान को सहेजे गए राज्य से मिलान नहीं किया जा सका।','शेताचे ठिकाण जतन केलेल्या राज्याशी जुळवता आले नाही.'],
    'Weather data is currently unavailable from the weather provider.':['मौसम सेवा से जानकारी अभी उपलब्ध नहीं है।','हवामान सेवेकडून माहिती सध्या उपलब्ध नाही.'],
    'Weather data is currently unavailable because this farm needs a specific location and state.':['मौसम के लिए खेत का विशिष्ट स्थान और राज्य आवश्यक है।','हवामानासाठी शेताचे विशिष्ट ठिकाण आणि राज्य आवश्यक आहे.'],
    'Precise soil-based crop recommendation requires soil information. Add values from an actual soil test report to continue.':['मिट्टी-आधारित फसल सुझाव के लिए वास्तविक मिट्टी परीक्षण रिपोर्ट के मान जोड़ें।','माती-आधारित पीक शिफारशीसाठी प्रत्यक्ष माती परीक्षण अहवालातील मूल्ये भरा.'],
    'Enter the values shown on your report. AgriPilot records that you entered and confirmed them; it does not independently verify the document.':['रिपोर्ट में दिए गए मान दर्ज करें। AgriPilot आपके दर्ज और पुष्टि किए मान सहेजता है; दस्तावेज़ की स्वतंत्र जांच नहीं करता।','अहवालातील मूल्ये भरा. AgriPilot तुम्ही भरलेली व निश्चित केलेली मूल्ये जतन करते; दस्तऐवजाची स्वतंत्र पडताळणी करत नाही.'],
    'Use current measured values. The rainfall window in the training data is not documented, so do not use the weather card as a substitute.':['अभी मापे गए मान दर्ज करें। प्रशिक्षण डेटा में वर्षा की अवधि दर्ज नहीं है, इसलिए मौसम कार्ड का विकल्प के रूप में उपयोग न करें।','सध्याची मोजलेली मूल्ये भरा. प्रशिक्षण डेटामधील पावसाचा कालावधी दिलेला नाही; त्यामुळे हवामान कार्डाचा पर्याय म्हणून वापर करू नका.'],
    'Unable to identify reliably.':['विश्वसनीय पहचान नहीं हो सकी।','विश्वसनीय ओळख पटली नाही.'],
    'The model’s crop result did not match the crop selected for this image. No disease result was saved. Check the crop selection and upload a clear leaf image.':['मॉडल की फसल पहचान चुनी गई फसल से मेल नहीं खाई। कोई रोग परिणाम सहेजा नहीं गया। फसल चयन जांचें और पत्ती की स्पष्ट तस्वीर अपलोड करें।','मॉडेलची पीक ओळख निवडलेल्या पिकाशी जुळली नाही. रोगाचा निकाल जतन केलेला नाही. पीक निवड तपासा आणि पानाचा स्पष्ट फोटो अपलोड करा.'],
    'Farm-specific irrigation/care context is unavailable; no measurement context was returned.':['खेत-विशिष्ट सिंचाई/देखभाल जानकारी उपलब्ध नहीं है; माप का संदर्भ नहीं मिला।','शेत-विशिष्ट सिंचन/काळजी माहिती उपलब्ध नाही; मोजमापांचा संदर्भ मिळाला नाही.'],
    'No farm records returned by the API.':['API से खेत का कोई रिकॉर्ड नहीं मिला।','API कडून शेताची कोणतीही नोंद मिळाली नाही.'],
    'Loading saved farm data…':['सहेजे खेत का डेटा लोड हो रहा है…','जतन केलेली शेत माहिती लोड होत आहे…'],
    'Farm profile saved.':['खेत प्रोफ़ाइल सहेजी गई।','शेत प्रोफाइल जतन केली.']
    ,'Farm name':['खेत का नाम','शेताचे नाव'], 'Location / village':['स्थान / गाँव','ठिकाण / गाव'],
    'District':['ज़िला','जिल्हा'], 'State':['राज्य','राज्य'], 'Select state':['राज्य चुनें','राज्य निवडा'],
    'Farm area (acres)':['खेत का क्षेत्रफल (एकड़)','शेताचे क्षेत्रफळ (एकर)'],
    'Current crop':['वर्तमान फसल','सध्याचे पीक'], 'Soil type':['मिट्टी का प्रकार','मातीचा प्रकार'],
    'Irrigation':['सिंचाई','सिंचन'], 'Select soil type':['मिट्टी का प्रकार चुनें','मातीचा प्रकार निवडा'],
    'Select irrigation':['सिंचाई चुनें','सिंचन निवडा'], 'Clay':['चिकनी मिट्टी','चिकणमाती'],
    'Clay loam':['चिकनी दोमट','चिकण दोमट'], 'Loam':['दोमट','पोयटायुक्त'],
    'Sandy':['रेतीली','वाळूमय'], 'Sandy loam':['रेतीली दोमट','वाळूमिश्रित पोयटा'],
    'Silt':['गादयुक्त मिट्टी','गाळाची माती'], 'Other / unsure':['अन्य / पता नहीं','इतर / खात्री नाही'],
    'Drip':['ड्रिप','ठिबक'], 'Sprinkler':['स्प्रिंकलर','तुषार'], 'Flood / surface':['सतही सिंचाई','पाटाने सिंचन'],
    'Rainfed':['वर्षा आधारित','पावसावर अवलंबून'], 'Enter your current crop':['अपनी वर्तमान फसल लिखें','तुमचे सध्याचे पीक लिहा'],
    'Set up your farm':['अपना खेत सेट करें','तुमचे शेत सेट करा'], 'Save farm details':['खेत का विवरण सहेजें','शेताची माहिती जतन करा'],
    'Farm profile':['खेत प्रोफ़ाइल','शेत प्रोफाइल'], 'Weather data is currently unavailable because this farm needs a specific location and state.':['मौसम के लिए खेत का विशिष्ट स्थान और राज्य आवश्यक है।','हवामानासाठी शेताचे विशिष्ट ठिकाण आणि राज्य आवश्यक आहे.'],
    'Ask about irrigation, costs, pests…':['सिंचाई, लागत या कीटों के बारे में पूछें…','सिंचन, खर्च किंवा किडींबद्दल विचारा…'],
    'temperature unavailable':['तापमान उपलब्ध नहीं','तापमान उपलब्ध नाही'], 'precipitation':['वर्षा','पर्जन्य'],
    'time unavailable':['समय उपलब्ध नहीं','वेळ उपलब्ध नाही'], 'timezone unavailable':['समय क्षेत्र उपलब्ध नहीं','वेळ क्षेत्र उपलब्ध नाही'],
    'Source:':['स्रोत:','स्रोत:'], 'Not available in the model response.':['मॉडल उत्तर में उपलब्ध नहीं।','मॉडेलच्या उत्तरात उपलब्ध नाही.'],
    'Grad-CAM was saved by the backend at':['Grad-CAM बैकएंड में यहां सहेजा गया:','Grad-CAM बॅकएंडमध्ये येथे जतन केले:'],
    'the API did not return image bytes.':['API ने चित्र डेटा नहीं लौटाया।','API ने चित्र डेटा परत केला नाही.'],
    'Grad-CAM was not returned for this request.':['इस अनुरोध के लिए Grad-CAM नहीं मिला।','या विनंतीसाठी Grad-CAM मिळाला नाही.'],
    'Farm irrigation/care context':['खेत सिंचाई/देखभाल संदर्भ','शेत सिंचन/काळजी संदर्भ'],
    'Ask Assistant about this result':['इस परिणाम के बारे में सहायक से पूछें','या निकालाबद्दल सहाय्यकाला विचारा']
  };
  let current = 'en';
  function t(value) { const item=words[String(value)]; return item ? (current==='en'?value:item[current==='hi'?0:1]||value) : value; }
  function apply() {
    document.documentElement.lang = current==='hi'?'hi':current==='mr'?'mr':'en';
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const value=el.dataset.i18n;
      const node=Array.from(el.childNodes).find(n=>n.nodeType===Node.TEXT_NODE);
      if(node) node.nodeValue=(node.nodeValue.match(/^\s*/)||[''])[0]+t(value);
      else el.textContent=t(value);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => el.placeholder=t(el.dataset.i18nPlaceholder));
    document.querySelectorAll('[data-i18n-title]').forEach(el => el.title=t(el.dataset.i18nTitle));
  }
  function setLanguage(value, persist=true) {
    current=['en','hi','mr'].includes(value)?value:'en';
    document.querySelectorAll('#api-lang,#app-language').forEach(el=>{if(el.value!==current)el.value=current;});
    if(persist) localStorage.setItem('agripilot-language',current);
    apply();
    document.dispatchEvent(new CustomEvent('agripilot-languagechange',{detail:{language:current}}));
  }
  window.AgriPilotI18n={t,setLanguage,getLanguage:()=>current,apply};
  document.addEventListener('DOMContentLoaded',()=>{
    const user=window.AGRIPILOT_CURRENT_USER;
    const stored=localStorage.getItem('agripilot-language');
    setLanguage(stored||user&&user.language||'en',!!stored);
    if(!stored&&!user) fetch('/api/auth/session',{credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(s=>{if(s&&s.user)setLanguage(s.user.language||'en',false);}).catch(()=>{});
    document.querySelectorAll('#api-lang,#app-language').forEach(el=>el.addEventListener('change',()=>setLanguage(el.value)));
  });
})();
