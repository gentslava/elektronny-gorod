/* eg-intercom-call-card — собранный бандл. Источник: frontend/src/. Не редактировать вручную. */
var Re=Object.defineProperty;var He=Object.getOwnPropertyDescriptor;var p=(r,e,t,i)=>{for(var s=i>1?void 0:i?He(e,t):e,o=r.length-1,n;o>=0;o--)(n=r[o])&&(s=(i?n(e,t,s):n(s))||s);return i&&s&&Re(e,t,s),s};var B=globalThis,V=B.ShadowRoot&&(B.ShadyCSS===void 0||B.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,X=Symbol(),ce=new WeakMap,H=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==X)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(V&&e===void 0){let i=t!==void 0&&t.length===1;i&&(e=ce.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&ce.set(t,e))}return e}toString(){return this.cssText}},le=r=>new H(typeof r=="string"?r:r+"",void 0,X),S=(r,...e)=>{let t=r.length===1?r[0]:e.reduce((i,s,o)=>i+(n=>{if(n._$cssResult$===!0)return n.cssText;if(typeof n=="number")return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s)+r[o+1],r[0]);return new H(t,r,X)},he=(r,e)=>{if(V)r.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let i=document.createElement("style"),s=B.litNonce;s!==void 0&&i.setAttribute("nonce",s),i.textContent=t.cssText,r.appendChild(i)}},Y=V?r=>r:r=>r instanceof CSSStyleSheet?(e=>{let t="";for(let i of e.cssRules)t+=i.cssText;return le(t)})(r):r;var{is:Ue,defineProperty:Oe,getOwnPropertyDescriptor:Ne,getOwnPropertyNames:je,getOwnPropertySymbols:De,getPrototypeOf:ze}=Object,W=globalThis,de=W.trustedTypes,Le=de?de.emptyScript:"",qe=W.reactiveElementPolyfillSupport,U=(r,e)=>r,O={toAttribute(r,e){switch(e){case Boolean:r=r?Le:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,e){let t=r;switch(e){case Boolean:t=r!==null;break;case Number:t=r===null?null:Number(r);break;case Object:case Array:try{t=JSON.parse(r)}catch{t=null}}return t}},K=(r,e)=>!Ue(r,e),pe={attribute:!0,type:String,converter:O,reflect:!1,useDefault:!1,hasChanged:K};Symbol.metadata??=Symbol("metadata"),W.litPropertyMetadata??=new WeakMap;var w=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=pe){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let i=Symbol(),s=this.getPropertyDescriptor(e,i,t);s!==void 0&&Oe(this.prototype,e,s)}}static getPropertyDescriptor(e,t,i){let{get:s,set:o}=Ne(this.prototype,e)??{get(){return this[t]},set(n){this[t]=n}};return{get:s,set(n){let c=s?.call(this);o?.call(this,n),this.requestUpdate(e,c,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??pe}static _$Ei(){if(this.hasOwnProperty(U("elementProperties")))return;let e=ze(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(U("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(U("properties"))){let t=this.properties,i=[...je(t),...De(t)];for(let s of i)this.createProperty(s,t[s])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[i,s]of t)this.elementProperties.set(i,s)}this._$Eh=new Map;for(let[t,i]of this.elementProperties){let s=this._$Eu(t,i);s!==void 0&&this._$Eh.set(s,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let s of i)t.unshift(Y(s))}else e!==void 0&&t.push(Y(e));return t}static _$Eu(e,t){let i=t.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return he(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){let i=this.constructor.elementProperties.get(e),s=this.constructor._$Eu(e,i);if(s!==void 0&&i.reflect===!0){let o=(i.converter?.toAttribute!==void 0?i.converter:O).toAttribute(t,i.type);this._$Em=e,o==null?this.removeAttribute(s):this.setAttribute(s,o),this._$Em=null}}_$AK(e,t){let i=this.constructor,s=i._$Eh.get(e);if(s!==void 0&&this._$Em!==s){let o=i.getPropertyOptions(s),n=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:O;this._$Em=s;let c=n.fromAttribute(t,o.type);this[s]=c??this._$Ej?.get(s)??c,this._$Em=null}}requestUpdate(e,t,i,s=!1,o){if(e!==void 0){let n=this.constructor;if(s===!1&&(o=this[e]),i??=n.getPropertyOptions(e),!((i.hasChanged??K)(o,t)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,i))))return;this.C(e,t,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:s,wrapped:o},n){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??t??this[e]),o!==!0||n!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),s===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[s,o]of this._$Ep)this[s]=o;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[s,o]of i){let{wrapped:n}=o,c=this[s];n!==!0||this._$AL.has(s)||c===void 0||this.C(s,void 0,o,c)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(t)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};w.elementStyles=[],w.shadowRootOptions={mode:"open"},w[U("elementProperties")]=new Map,w[U("finalized")]=new Map,qe?.({ReactiveElement:w}),(W.reactiveElementVersions??=[]).push("2.1.2");var re=globalThis,ue=r=>r,F=re.trustedTypes,me=F?F.createPolicy("lit-html",{createHTML:r=>r}):void 0,ye="$lit$",A=`lit$${Math.random().toFixed(9).slice(2)}$`,$e="?"+A,Ie=`<${$e}>`,E=document,j=()=>E.createComment(""),D=r=>r===null||typeof r!="object"&&typeof r!="function",oe=Array.isArray,Be=r=>oe(r)||typeof r?.[Symbol.iterator]=="function",Z=`[ 	
\f\r]`,N=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,fe=/-->/g,_e=/>/g,k=RegExp(`>|${Z}(?:([^\\s"'>=/]+)(${Z}*=${Z}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ge=/'/g,ve=/"/g,we=/^(?:script|style|textarea|title)$/i,ne=r=>(e,...t)=>({_$litType$:r,strings:e,values:t}),h=ne(1),ht=ne(2),dt=ne(3),C=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),be=new WeakMap,P=E.createTreeWalker(E,129);function xe(r,e){if(!oe(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return me!==void 0?me.createHTML(e):e}var Ve=(r,e)=>{let t=r.length-1,i=[],s,o=e===2?"<svg>":e===3?"<math>":"",n=N;for(let c=0;c<t;c++){let a=r[c],u,m,d=-1,v=0;for(;v<a.length&&(n.lastIndex=v,m=n.exec(a),m!==null);)v=n.lastIndex,n===N?m[1]==="!--"?n=fe:m[1]!==void 0?n=_e:m[2]!==void 0?(we.test(m[2])&&(s=RegExp("</"+m[2],"g")),n=k):m[3]!==void 0&&(n=k):n===k?m[0]===">"?(n=s??N,d=-1):m[1]===void 0?d=-2:(d=n.lastIndex-m[2].length,u=m[1],n=m[3]===void 0?k:m[3]==='"'?ve:ge):n===ve||n===ge?n=k:n===fe||n===_e?n=N:(n=k,s=void 0);let b=n===k&&r[c+1].startsWith("/>")?" ":"";o+=n===N?a+Ie:d>=0?(i.push(u),a.slice(0,d)+ye+a.slice(d)+A+b):a+A+(d===-2?c:b)}return[xe(r,o+(r[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},z=class r{constructor({strings:e,_$litType$:t},i){let s;this.parts=[];let o=0,n=0,c=e.length-1,a=this.parts,[u,m]=Ve(e,t);if(this.el=r.createElement(u,i),P.currentNode=this.el.content,t===2||t===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(s=P.nextNode())!==null&&a.length<c;){if(s.nodeType===1){if(s.hasAttributes())for(let d of s.getAttributeNames())if(d.endsWith(ye)){let v=m[n++],b=s.getAttribute(d).split(A),I=/([.?@])?(.*)/.exec(v);a.push({type:1,index:o,name:I[2],strings:b,ctor:I[1]==="."?ee:I[1]==="?"?te:I[1]==="@"?ie:M}),s.removeAttribute(d)}else d.startsWith(A)&&(a.push({type:6,index:o}),s.removeAttribute(d));if(we.test(s.tagName)){let d=s.textContent.split(A),v=d.length-1;if(v>0){s.textContent=F?F.emptyScript:"";for(let b=0;b<v;b++)s.append(d[b],j()),P.nextNode(),a.push({type:2,index:++o});s.append(d[v],j())}}}else if(s.nodeType===8)if(s.data===$e)a.push({type:2,index:o});else{let d=-1;for(;(d=s.data.indexOf(A,d+1))!==-1;)a.push({type:7,index:o}),d+=A.length-1}o++}}static createElement(e,t){let i=E.createElement("template");return i.innerHTML=e,i}};function T(r,e,t=r,i){if(e===C)return e;let s=i!==void 0?t._$Co?.[i]:t._$Cl,o=D(e)?void 0:e._$litDirective$;return s?.constructor!==o&&(s?._$AO?.(!1),o===void 0?s=void 0:(s=new o(r),s._$AT(r,t,i)),i!==void 0?(t._$Co??=[])[i]=s:t._$Cl=s),s!==void 0&&(e=T(r,s._$AS(r,e.values),s,i)),e}var Q=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:i}=this._$AD,s=(e?.creationScope??E).importNode(t,!0);P.currentNode=s;let o=P.nextNode(),n=0,c=0,a=i[0];for(;a!==void 0;){if(n===a.index){let u;a.type===2?u=new L(o,o.nextSibling,this,e):a.type===1?u=new a.ctor(o,a.name,a.strings,this,e):a.type===6&&(u=new se(o,this,e)),this._$AV.push(u),a=i[++c]}n!==a?.index&&(o=P.nextNode(),n++)}return P.currentNode=E,s}p(e){let t=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}},L=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,s){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=T(this,e,t),D(e)?e===l||e==null||e===""?(this._$AH!==l&&this._$AR(),this._$AH=l):e!==this._$AH&&e!==C&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Be(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==l&&D(this._$AH)?this._$AA.nextSibling.data=e:this.T(E.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:i}=e,s=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=z.createElement(xe(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(t);else{let o=new Q(s,this),n=o.u(this.options);o.p(t),this.T(n),this._$AH=o}}_$AC(e){let t=be.get(e.strings);return t===void 0&&be.set(e.strings,t=new z(e)),t}k(e){oe(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,i,s=0;for(let o of e)s===t.length?t.push(i=new r(this.O(j()),this.O(j()),this,this.options)):i=t[s],i._$AI(o),s++;s<t.length&&(this._$AR(i&&i._$AB.nextSibling,s),t.length=s)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let i=ue(e).nextSibling;ue(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},M=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,s,o){this.type=1,this._$AH=l,this._$AN=void 0,this.element=e,this.name=t,this._$AM=s,this.options=o,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=l}_$AI(e,t=this,i,s){let o=this.strings,n=!1;if(o===void 0)e=T(this,e,t,0),n=!D(e)||e!==this._$AH&&e!==C,n&&(this._$AH=e);else{let c=e,a,u;for(e=o[0],a=0;a<o.length-1;a++)u=T(this,c[i+a],t,a),u===C&&(u=this._$AH[a]),n||=!D(u)||u!==this._$AH[a],u===l?e=l:e!==l&&(e+=(u??"")+o[a+1]),this._$AH[a]=u}n&&!s&&this.j(e)}j(e){e===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},ee=class extends M{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===l?void 0:e}},te=class extends M{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==l)}},ie=class extends M{constructor(e,t,i,s,o){super(e,t,i,s,o),this.type=5}_$AI(e,t=this){if((e=T(this,e,t,0)??l)===C)return;let i=this._$AH,s=e===l&&i!==l||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==l&&(i===l||s);s&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},se=class{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){T(this,e)}};var We=re.litHtmlPolyfillSupport;We?.(z,L),(re.litHtmlVersions??=[]).push("3.3.3");var Ae=(r,e,t)=>{let i=t?.renderBefore??e,s=i._$litPart$;if(s===void 0){let o=t?.renderBefore??null;i._$litPart$=s=new L(e.insertBefore(j(),o),o,void 0,t??{})}return s._$AI(r),s};var ae=globalThis,y=class extends w{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Ae(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return C}};y._$litElement$=!0,y.finalized=!0,ae.litElementHydrateSupport?.({LitElement:y});var Ke=ae.litElementPolyfillSupport;Ke?.({LitElement:y});(ae.litElementVersions??=[]).push("4.2.2");var R=r=>(e,t)=>{t!==void 0?t.addInitializer(()=>{customElements.define(r,e)}):customElements.define(r,e)};var Fe={attribute:!0,type:String,converter:O,reflect:!1,hasChanged:K},Je=(r=Fe,e,t)=>{let{kind:i,metadata:s}=t,o=globalThis.litPropertyMetadata.get(s);if(o===void 0&&globalThis.litPropertyMetadata.set(s,o=new Map),i==="setter"&&((r=Object.create(r)).wrapped=!0),o.set(t.name,r),i==="accessor"){let{name:n}=t;return{set(c){let a=e.get.call(this);e.set.call(this,c),this.requestUpdate(n,a,r,!0,c)},init(c){return c!==void 0&&this.C(n,void 0,r,c),c}}}if(i==="setter"){let{name:n}=t;return function(c){let a=this[n];e.call(this,c),this.requestUpdate(n,a,r,!0,c)}}throw Error("Unsupported decorator location: "+i)};function f(r){return(e,t)=>typeof t=="object"?Je(r,e,t):((i,s,o)=>{let n=s.hasOwnProperty(o);return s.constructor.createProperty(o,i),n?Object.getOwnPropertyDescriptor(s,o):void 0})(r,e,t)}function _(r){return f({...r,state:!0,attribute:!1})}var Ge=new Set(["idle","ringing","connecting","active","ended","error"]);function Se(r){return r&&Ge.has(r)?r:"idle"}var q={visible:!1,video:"none",showAccept:!1,showReject:!1,showHangup:!1,showOpen:!1,showMic:!1,showTimer:!1,busy:!1,isError:!1};function ke(r){switch(r){case"ringing":return{...q,visible:!0,video:"doorbell",showAccept:!0,showReject:!0,showOpen:!0};case"connecting":return{...q,visible:!0,video:"doorbell",showReject:!0,showOpen:!0,busy:!0};case"active":return{...q,visible:!0,video:"call",showHangup:!0,showOpen:!0,showMic:!0,showTimer:!0};case"error":return{...q,visible:!0,video:"none",showHangup:!0,showOpen:!0,isError:!0};case"idle":case"ended":default:return{...q}}}function Pe(r,e){if(r==="call")return e.camera;if(r==="doorbell")return e.doorbell_camera??e.camera}var x=class extends y{constructor(){super(...arguments);this.muted=!1;this._provider="pending"}connectedCallback(){super.connectedCallback(),this._resolveProvider()}async _resolveProvider(){if(customElements.get("ha-camera-stream")){this._provider="ha";return}try{await window.loadCardHelpers?.()}catch{}customElements.get("ha-camera-stream")?this._provider="ha":customElements.get("webrtc-camera")?this._provider="webrtc":this._provider="none"}updated(t){this._provider==="webrtc"&&this._syncWebrtc(t)}_syncWebrtc(t){let i=this.renderRoot.querySelector("#webrtc-host");if(!(!i||!this.entity||!this.hass))if(t.has("entity")||t.has("_provider")||t.has("muted")||!this._webrtcEl){i.replaceChildren();let s=document.createElement("webrtc-camera");s.setConfig({entity:this.entity,muted:this.muted}),s.hass=this.hass,i.appendChild(s),this._webrtcEl=s}else this._webrtcEl.hass=this.hass}render(){if(!this.entity||!this.hass)return this._frame("mdi:cctv-off","\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u0438\u0434\u0435\u043E");let t=this.hass.states[this.entity];if(!t)return this._frame("mdi:cctv-off","\u041A\u0430\u043C\u0435\u0440\u0430 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u0430");switch(this._provider){case"pending":return this._frame("mdi:loading","\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0432\u0438\u0434\u0435\u043E\u2026");case"ha":return h`
          <ha-camera-stream
            .hass=${this.hass}
            .stateObj=${t}
            .muted=${this.muted}
            controls
          ></ha-camera-stream>
        `;case"webrtc":return h`<div id="webrtc-host"></div>`;default:return this._frame("mdi:cctv-off","\u0412\u0438\u0434\u0435\u043E\u043F\u043B\u0435\u0435\u0440 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D \u2014 \u043E\u0431\u043D\u043E\u0432\u0438\u0442\u0435 HA \u0438\u043B\u0438 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0435 advanced-camera-card")}}_frame(t,i){return h`
      <div class="frame" role="img" aria-label=${i}>
        <ha-icon icon=${t}></ha-icon>
        <span>${i}</span>
      </div>
      ${l}
    `}};x.styles=S`
    :host {
      display: block;
      width: 100%;
      height: 100%;
    }
    ha-camera-stream,
    #webrtc-host {
      display: block;
      width: 100%;
      height: 100%;
    }
    /* реальный плеер заполняет область (object-fit самого видео — по потоку) */
    .frame {
      width: 100%;
      height: 100%;
      background: var(--secondary-background-color);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: var(--secondary-text-color);
      text-align: center;
      padding: 8px;
      box-sizing: border-box;
    }
    .frame ha-icon {
      --mdc-icon-size: 40px;
    }
    .frame span {
      font-size: 0.85rem;
    }
  `,p([f({attribute:!1})],x.prototype,"hass",2),p([f()],x.prototype,"entity",2),p([f({type:Boolean})],x.prototype,"muted",2),p([_()],x.prototype,"_provider",2),x=p([R("eg-call-video")],x);function Ee(r){return r<0?0:r>1?1:r}function Xe(r,e,t,i){let s=Math.max(1,t-i);return Ee((r-e-i/2)/s)}function Ye(r,e){return Ee(r/Math.max(1,e))}var Ze=.92,Qe=800,$=class extends y{constructor(){super(...arguments);this.mode="hold";this.disabled=!1;this.label="\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C";this.status="idle";this._progress=0;this._arming=!1;this._raf=0;this._holdStart=0;this._trackRect=null;this._holdTick=()=>{if(this._progress=Ye(performance.now()-this._holdStart,Qe),this._progress>=1){this._reset(),this._fireOpen();return}this._raf=requestAnimationFrame(this._holdTick)};this._onHoldDown=t=>{this.disabled||(t.target.setPointerCapture?.(t.pointerId),this._arming=!0,this._holdStart=performance.now(),this._raf=requestAnimationFrame(this._holdTick))};this._onHoldUp=()=>{this._progress<1&&this._reset()};this._onSlideDown=t=>{if(this.disabled)return;let i=t.currentTarget.closest(".track");this._trackRect=i?.getBoundingClientRect()??null,t.target.setPointerCapture?.(t.pointerId),this._arming=!0};this._onSlideMove=t=>{if(!this._arming||!this._trackRect)return;let i=60;this._progress=Xe(t.clientX,this._trackRect.left,this._trackRect.width,i)};this._onSlideUp=()=>{this._progress>=Ze?(this._reset(),this._fireOpen()):this._reset()};this._onTap=()=>{this.disabled||this._fireOpen()}}_fireOpen(){this.dispatchEvent(new CustomEvent("open",{bubbles:!0,composed:!0}))}_reset(){this._raf&&cancelAnimationFrame(this._raf),this._raf=0,this._arming=!1,this._progress=0,this._trackRect=null}render(){return this.mode==="tap"?this._renderTap():this.mode==="slide"?this._renderSlide():this._renderHold()}_caption(){return this.status==="opening"?"\u041E\u0442\u043A\u0440\u044B\u0432\u0430\u044E\u2026":this.status==="opened"?"\u041E\u0442\u043A\u0440\u044B\u0442\u043E":this.status==="error"?"\u041E\u0448\u0438\u0431\u043A\u0430":this.mode==="hold"?"\u0423\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0439\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C":"\u041E\u0442\u043A\u0440\u044B\u0442\u044C"}_iconName(){return this.status==="opened"?"mdi:lock-open-variant":this.status==="error"?"mdi:lock-alert":"mdi:lock"}_knobIcon(){return this.status==="opened"?"mdi:lock-open-variant":this.status==="error"?"mdi:lock-alert":"mdi:key-variant"}_vp(){return this.status==="opened"||this.status==="error"?1:this._progress}_statusClass(){return this.status==="opened"?"st-opened":this.status==="error"?"st-error":this.status==="opening"?"st-opening":""}_renderTap(){return h`
      <button class="bar tap ${this._statusClass()}" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this.label}>
        <div class="fill" style="width:${this._vp()*100}%"></div>
        <span class="bar-label"><ha-icon icon=${this._iconName()}></ha-icon>${this._caption()}</span>
      </button>
    `}_renderHold(){return h`
      <button
        class="bar hold ${this._arming?"arming":""} ${this._statusClass()}"
        ?disabled=${this.disabled}
        aria-label="${this.label} — удерживайте"
        @pointerdown=${this._onHoldDown}
        @pointerup=${this._onHoldUp}
        @pointercancel=${this._onHoldUp}
        @pointerleave=${this._onHoldUp}
      >
        <div class="fill" style="width:${this._vp()*100}%"></div>
        <span class="bar-label">
          <ha-icon icon=${this._iconName()}></ha-icon>
          ${this._caption()}
        </span>
      </button>
    `}_renderSlide(){let t=this._vp();return h`
      <div
        class="track ${this._statusClass()} ${this._arming?"dragging":""}"
        style="--eg-prog:${t}"
        role="slider"
        aria-label=${this.label}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(t*100)}
      >
        <ha-icon class="hint hint-l" icon="mdi:lock" aria-hidden="true"></ha-icon>
        <ha-icon class="hint hint-r" icon="mdi:lock-open-variant" aria-hidden="true"></ha-icon>
        <div class="fill"></div>
        <span class="bar-label">${this._caption()}</span>
        <div
          class="knob ${this.disabled?"off":""}"
          @pointerdown=${this._onSlideDown}
          @pointermove=${this._onSlideMove}
          @pointerup=${this._onSlideUp}
          @pointercancel=${this._onSlideUp}
        >
          <ha-icon icon=${this._knobIcon()}></ha-icon>
        </div>
      </div>
    `}};$.styles=S`
    :host {
      display: block;
    }
    .bar,
    .track {
      position: relative;
      overflow: hidden;
      min-height: 68px;
      border-radius: 34px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      font-weight: 600;
      font-size: 1.05rem;
      user-select: none;
      touch-action: none;
    }
    .bar {
      width: 100%;
      max-width: 340px;
      margin: 0 auto;
      border: none;
      cursor: pointer;
      font: inherit;
      font-weight: 600;
    }
    /* слайдер — подтверждение действия: узкий, не во всю ширину (как в оригинале) */
    .track {
      box-sizing: border-box;
      width: 100%;
      max-width: 300px;
      margin: 0 auto;
      --knob: 60px; /* крупная цель под палец: > 48dp Material / 44pt Apple HIG */
    }
    .bar[disabled] {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .fill {
      position: absolute;
      inset: 0 auto 0 0;
      /* Открыть = accent (НЕ красный — красный за «Завершить», см. spec §3). */
      background: var(--primary-color);
      opacity: 0.16;
      transition: width 80ms linear;
    }
    /* на слайдере заливка следует за кнопкой через --eg-prog (тот же источник, без лага) */
    .track .fill {
      width: calc(var(--eg-prog, 0) * 100%);
    }
    .track.dragging .fill {
      transition: none;
    }
    .bar-label,
    .bar > span {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      z-index: 1;
    }
    /* подсказки направления: закрытый замок слева (старт), открытый справа (цель) */
    .hint {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      --mdc-icon-size: 22px;
      color: var(--secondary-text-color);
      opacity: 0.5;
      z-index: 0;
    }
    .hint-l {
      left: 20px;
    }
    .hint-r {
      right: 20px;
    }
    /* кружок слайдера: позиция строго по прогрессу (CSS left от --eg-prog, без JS-трансформа) */
    .knob {
      position: absolute;
      top: 4px;
      left: calc(var(--eg-prog, 0) * (100% - var(--knob, 60px)));
      width: var(--knob, 60px);
      height: var(--knob, 60px);
      border-radius: 50%;
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: grab;
      touch-action: none;
      z-index: 2;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.28);
      transition: left 0.18s ease;
    }
    .track.dragging .knob {
      transition: none;
      cursor: grabbing;
    }
    .knob.off {
      opacity: 0.5;
    }
    .knob ha-icon {
      --mdc-icon-size: 26px;
    }
    .bar ha-icon {
      --mdc-icon-size: 24px;
    }
    /* «Открыто»/«Ошибка»: на плашке hold/tap — вся плашка; на слайдере — ТОЛЬКО кнопка */
    .bar.st-opened .fill {
      background: var(--success-color, #2e7d32);
      opacity: 1;
    }
    .bar.st-error .fill {
      background: var(--error-color, #c62828);
      opacity: 1;
    }
    .bar.st-opened .bar-label,
    .bar.st-error .bar-label {
      color: #fff;
    }
    .bar.st-opened ha-icon,
    .bar.st-error ha-icon {
      color: #fff;
    }
    .track.st-opened .knob {
      background: var(--success-color, #2e7d32);
    }
    .track.st-error .knob {
      background: var(--error-color, #c62828);
    }
    @media (prefers-reduced-motion: reduce) {
      .fill,
      .knob {
        transition: none;
      }
    }
  `,p([f()],$.prototype,"mode",2),p([f({type:Boolean})],$.prototype,"disabled",2),p([f()],$.prototype,"label",2),p([f()],$.prototype,"status",2),p([_()],$.prototype,"_progress",2),p([_()],$.prototype,"_arming",2),$=p([R("eg-open-control")],$);function Ce(r,e){return e&&r==="granted"}var G=class{constructor(e,t=()=>{}){this._getConn=e;this._onChange=t;this.active=!1;this.lastError=""}async queryPermission(){try{return(await navigator.permissions?.query({name:"microphone"}))?.state??"unknown"}catch{return"unknown"}}get secure(){return typeof window<"u"&&window.isSecureContext===!0}async start(){if(this.active)return;let e=this._getConn();if(!e){this._fail("\u043D\u0435\u0442 \u0441\u0432\u044F\u0437\u0438 \u0441 Home Assistant");return}if(!navigator.mediaDevices?.getUserMedia){this._fail("\u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D (\u043D\u0443\u0436\u0435\u043D HTTPS-origin)");return}try{let t=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0}}),i=window.AudioContext||window.webkitAudioContext,s=new i,o=s.sampleRate,n=this._sub;(!n||n.sampleRate!==o)&&(n={handlerId:(await e.sendMessagePromise({type:"elektronny_gorod/intercom_uplink",sample_rate:o})).handler_id,sampleRate:o},this._sub=n);let c=n.handlerId,a=e.socket;await s.audioWorklet.addModule(this._workletUrl());let u=new AudioWorkletNode(s,"eg-pcm-int16",{numberOfOutputs:0});u.port.onmessage=d=>{let v=d.data,b=new Uint8Array(1+v.byteLength);b[0]=c,b.set(new Uint8Array(v.buffer),1),a.readyState===1&&a.send(b)};let m=s.createMediaStreamSource(t);m.connect(u),this._ctx={ac:s,stream:t,node:u,src:m},this.active=!0,this.lastError="",this._onChange()}catch(t){this._fail(t instanceof Error?t.message:String(t))}}stop(){let e=this._ctx;if(e){try{e.node.port.onmessage=null,e.node.disconnect(),e.src.disconnect()}catch{}try{e.stream.getTracks().forEach(t=>t.stop())}catch{}try{e.ac.close()}catch{}}if(this._ctx=void 0,this.active=!1,this._wUrl){try{URL.revokeObjectURL(this._wUrl)}catch{}this._wUrl=void 0}this._onChange()}_fail(e){this.lastError=e,this.stop()}_workletUrl(){if(this._wUrl)return this._wUrl;let e=`
      class EgPcmInt16 extends AudioWorkletProcessor {
        process(inputs) {
          const ch = inputs[0] && inputs[0][0];
          if (ch && ch.length) {
            const i16 = new Int16Array(ch.length);
            for (let i = 0; i < ch.length; i++) {
              const s = Math.max(-1, Math.min(1, ch[i]));
              i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
            }
            this.port.postMessage(i16, [i16.buffer]);
          }
          return true;
        }
      }
      registerProcessor("eg-pcm-int16", EgPcmInt16);`;return this._wUrl=URL.createObjectURL(new Blob([e],{type:"application/javascript"})),this._wUrl}};var et=new Set(["slide","hold","tap"]);function Te(r,e){return r&&et.has(r)?r:e?"slide":"hold"}function Me(){return typeof window<"u"&&typeof window.matchMedia=="function"&&window.matchMedia("(pointer: coarse)").matches}var tt={ringing:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432",connecting:"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026",active:"\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440",ended:"\u0412\u044B\u0437\u043E\u0432 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D",error:"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430"},it=new Set(["ringing","connecting","active","error"]),st=6e3,rt=3e3,g=class extends y{constructor(){super(...arguments);this._config={};this._muted=!1;this._micActive=!1;this._micPerm="unknown";this._openStatus="idle";this._now=Date.now();this._errDismissed=new Set;this._doorbells=[];this._openAction="hold";this._prevKey="";this._mic=new G(()=>this.hass?.connection,()=>{this._micActive=this._mic.active,this.requestUpdate()});this._answer=()=>{this.hass?.callService("elektronny_gorod","answer")};this._hangup=()=>{this.hass?.callService("elektronny_gorod","hangup")};this._toggleMute=()=>{this._muted=!this._muted};this._toggleMic=async()=>{this._mic.active?this._mic.stop():await this._mic.start(),this._micPerm=await this._mic.queryPermission()};this._open=async()=>{let t=this._active?.lock;if(!(!t||!this.hass)){this._openStatus="opening";try{await this.hass.callService("lock","unlock",{entity_id:t}),this._openStatus="opened"}catch{this._openStatus="error"}this._openReset&&clearTimeout(this._openReset),this._openReset=window.setTimeout(()=>{this._openStatus="idle",this.requestUpdate()},rt)}}}setConfig(t){let i=t?.doorbells??(t?.call_state?[{call_state:t.call_state,doorbell_camera:t.doorbell_camera,lock:t.lock,name:t.name}]:[]);if(!i.length||i.some(s=>!s.call_state))throw new Error("eg-intercom-call-card: \u0443\u043A\u0430\u0436\u0438\u0442\u0435 'doorbells' (\u0441 call_state) \u0438\u043B\u0438 'call_state'");this._config=t,this._doorbells=i,this._openAction=Te(t.open_action,Me())}getCardSize(){return 8}static getStubConfig(){return{camera:"",doorbells:[{call_state:"",doorbell_camera:"",lock:""}]}}disconnectedCallback(){super.disconnectedCallback(),this._mic.stop(),this._stopTick(),this._errHide&&clearTimeout(this._errHide),this._openReset&&clearTimeout(this._openReset)}_phaseOf(t){let i=this.hass?.states[t.call_state]?.state;return Se(i)}get _active(){return this._doorbells.find(t=>it.has(this._phaseOf(t))&&!this._errDismissed.has(t.call_state))}get _phase(){let t=this._active;return t?this._phaseOf(t):"idle"}get _intercomName(){let t=this._active,s=(t?this.hass?.states[t.call_state]?.attributes:void 0)?.intercom_name;return(typeof s=="string"?s.replace(/\s+/g," ").trim():"")||t?.name||this._config.name||"\u0414\u043E\u043C\u043E\u0444\u043E\u043D"}get _startedAtMs(){let t=this._active,i=t?this.hass?.states[t.call_state]?.attributes?.started_at:void 0;if(typeof i!="string")return;let s=Date.parse(i);return Number.isNaN(s)?void 0:s}willUpdate(t){if(!t.has("hass"))return;for(let o of this._doorbells)this._errDismissed.has(o.call_state)&&this._phaseOf(o)!=="error"&&this._errDismissed.delete(o.call_state);let i=this._active,s=i?`${i.call_state}|${this._phaseOf(i)}`:"idle";s!==this._prevKey&&(this._onPhase(this._phase,i),this._prevKey=s)}_onPhase(t,i){t==="active"?this._enterActive():this._exitActive(),t==="error"&&i&&this._scheduleErrDismiss(i.call_state),(t==="idle"||t==="ringing")&&(this._openStatus="idle")}async _enterActive(){this._muted=!1,this._startTick(),this._micPerm=await this._mic.queryPermission(),this._config.mic_autostart!==!1&&Ce(this._micPerm,this._mic.secure)&&await this._mic.start()}_exitActive(){this._mic.stop(),this._stopTick()}_startTick(){this._stopTick(),this._now=Date.now(),this._tick=window.setInterval(()=>{this._now=Date.now()},1e3)}_stopTick(){this._tick&&(clearInterval(this._tick),this._tick=void 0)}_scheduleErrDismiss(t){this._errHide&&clearTimeout(this._errHide),this._errHide=window.setTimeout(()=>{this._errDismissed=new Set(this._errDismissed).add(t),this.requestUpdate()},st)}_timerText(){let t=this._startedAtMs;if(t===void 0)return"";let i=Math.max(0,Math.floor((this._now-t)/1e3)),s=String(Math.floor(i/60)).padStart(2,"0"),o=String(i%60).padStart(2,"0");return`${s}:${o}`}render(){let t=this._active;if(!t)return this._renderIdle();let i=this._phase,s=ke(i),o=Pe(s.video,{camera:this._config.camera,doorbell_camera:t.doorbell_camera}),n=s.showTimer&&this._config.timer!=="off";return h`
      <ha-card class="phase-${i}">
        <div class="media">
          <header>
            <span class="name" title=${this._intercomName}>${this._intercomName}</span>
            <span class="status ${s.isError?"err":""}">
              ${s.busy?h`<span class="dot" aria-hidden="true"></span>`:l}
              <span>${tt[i]??""}</span>
              ${n?h`<span class="timer">${this._timerText()}</span>`:l}
            </span>
          </header>

          <div class="stage">
            ${o?h`<eg-call-video .hass=${this.hass} .entity=${o} .muted=${this._muted}></eg-call-video>`:s.isError?h`<div class="frame err"><ha-icon icon="mdi:phone-alert"></ha-icon><span>Не удалось установить вызов</span></div>`:l}
            ${s.busy?h`<div class="connecting" aria-hidden="true"><div class="spinner"></div></div>`:l}
          </div>
        </div>

        <div class="controls">
          <div class="open-area">
            ${s.showOpen?this._renderOpen():l}
          </div>
          ${this._renderActions(s)}
        </div>
      </ha-card>
    `}_doorbellNames(){return this._doorbells.map(t=>{let i=this.hass?.states[t.call_state]?.attributes?.intercom_name;return t.name??(typeof i=="string"?i:"")}).filter(Boolean)}_renderIdle(){let t=this._doorbellNames();return h`
      <ha-card class="idle">
        <div class="idle-stage" role="status">
          <ha-icon icon="mdi:doorbell-video"></ha-icon>
          <div class="idle-title">${this._config.idle_text??"\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u044B\u0437\u043E\u0432\u0430"}</div>
          <div class="idle-sub">Экран покажет видео, звук и кнопки при звонке домофона</div>
          ${t.length?h`<div class="idle-chips">
                ${t.map(i=>h`<span class="chip"><ha-icon icon="mdi:check-circle"></ha-icon>${i}</span>`)}
              </div>`:l}
        </div>
      </ha-card>
    `}_renderOpen(){return h`
      <eg-open-control
        .mode=${this._openAction}
        .status=${this._openStatus}
        ?disabled=${!this._active?.lock}
        @open=${this._open}
      ></eg-open-control>
    `}_renderActions(t){return t.showAccept||t.showReject&&!t.showHangup?h`
        <div class="actions">
          ${t.showReject?h`<button class="circle reject" @click=${this._hangup}>
                  <ha-icon icon="mdi:phone-hangup"></ha-icon><small>Отклонить</small>
                </button>`:l}
          ${t.showAccept?h`<button class="circle accept" @click=${this._answer}>
                  <ha-icon icon="mdi:phone"></ha-icon><small>Принять</small>
                </button>`:l}
        </div>
      `:t.showHangup?h`
        <div class="actions">
          ${t.showMic&&this._config.mic!==!1?this._renderMic():l}
          ${t.showMic?h`<button class="circle" @click=${this._toggleMute}
                    aria-label=${this._muted?"\u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u0437\u0432\u0443\u043A":"\u0412\u044B\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u0437\u0432\u0443\u043A"}>
                  <ha-icon icon=${this._muted?"mdi:volume-off":"mdi:volume-high"}></ha-icon>
                  <small>${this._muted?"\u0417\u0432\u0443\u043A":"\u0414\u0438\u043D\u0430\u043C\u0438\u043A"}</small>
                </button>`:l}
          <button class="circle reject" @click=${this._hangup} aria-label="Завершить">
            <ha-icon icon="mdi:phone-hangup"></ha-icon><small>Завершить</small>
          </button>
        </div>
      `:h`<div class="actions"></div>`}_renderMic(){return this._mic.secure?this._micPerm==="denied"?h`<button class="circle" disabled aria-label="Доступ к микрофону запрещён" title="Разрешите микрофон в настройках браузера">
        <ha-icon icon="mdi:microphone-off"></ha-icon><small>Запрещён</small>
      </button>`:this._micActive?h`<button class="circle mic-on" @click=${this._toggleMic} aria-label="Выключить микрофон">
        <ha-icon icon="mdi:microphone"></ha-icon><small>Микрофон</small>
      </button>`:this._micPerm!=="granted"?h`<button class="circle" @click=${this._toggleMic} aria-label="Разрешить микрофон">
        <ha-icon icon="mdi:microphone-question"></ha-icon><small>Разрешить</small>
      </button>`:h`<button class="circle" @click=${this._toggleMic} aria-label="Включить микрофон">
      <ha-icon icon="mdi:microphone-off"></ha-icon><small>Микрофон</small>
    </button>`:h`<button class="circle" disabled aria-label="Микрофон требует HTTPS" title="Микрофон доступен только по HTTPS">
        <ha-icon icon="mdi:microphone-off"></ha-icon><small>Нет HTTPS</small>
      </button>`}};g.styles=S`
    :host {
      display: block;
      height: 100%;
      /* адаптив по собственной ширине карточки (телефон / планшет-ландшафт / десктоп) */
      container-type: inline-size;
    }
    ha-card {
      height: 100%;
      box-sizing: border-box;
      /* щедрые отступы от краёв экрана + безопасные зоны */
      padding: max(20px, env(safe-area-inset-top))
        max(20px, env(safe-area-inset-right))
        max(20px, env(safe-area-inset-bottom))
        max(20px, env(safe-area-inset-left));
      display: flex;
      flex-direction: column;
      /* телефон: равномерные промежутки вокруг видео; на низком экране схлопываются */
      justify-content: space-evenly;
      gap: 12px;
    }
    .media {
      display: flex;
      flex-direction: column;
      gap: 12px;
      flex: none; /* видео фиксированной высоты (16:9 по ширине), не пляшет */
    }
    .stage {
      position: relative;
      /* видео всегда полная ширина и 16:9 (не «окошко», не ужимается по высоте) */
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 12px;
      overflow: hidden;
      background: var(--secondary-background-color);
    }
    .stage > eg-call-video {
      position: absolute;
      inset: 0;
    }
    /* телефон: open и actions — прямые flex-элементы карточки (равномерно вокруг видео) */
    .controls {
      display: contents;
    }
    .open-area {
      display: flex;
      justify-content: center;
      flex: none;
    }
    .open-area eg-open-control {
      width: 100%;
    }
    /* idle-заглушка «Нет активного вызова» — «призрак» экрана вызова */
    ha-card.idle {
      align-items: stretch;
      justify-content: center;
    }
    .idle-stage {
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 12px;
      background: var(--secondary-background-color);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      text-align: center;
      padding: 14px;
      box-sizing: border-box;
      color: var(--secondary-text-color);
    }
    .idle-stage ha-icon {
      --mdc-icon-size: 52px;
      color: var(--primary-color);
      opacity: 0.75;
    }
    .idle-title {
      font-size: 1.3rem;
      font-weight: 700;
      color: var(--primary-text-color);
    }
    .idle-sub {
      font-size: 0.95rem;
      max-width: 34ch;
    }
    .idle-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
      margin-top: 8px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 5px 12px 5px 8px;
      border-radius: 999px;
      background: var(--card-background-color, var(--ha-card-background));
      color: var(--primary-text-color);
      font-size: 0.8rem;
      font-weight: 600;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
    }
    .chip ha-icon {
      --mdc-icon-size: 16px;
      color: var(--success-color, #4caf50);
      opacity: 1;
    }
    /* широкий контейнер — планшет-ландшафт / десктоп: 2 колонки */
    @container (min-width: 640px) {
      ha-card {
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        gap: 18px;
      }
      ha-card.idle {
        flex-direction: column;
        justify-content: center;
        align-items: center;
      }
      ha-card.idle .idle-stage {
        max-width: 760px;
        gap: 10px;
        padding: 28px;
      }
      ha-card.idle .idle-stage ha-icon {
        --mdc-icon-size: 80px;
      }
      ha-card.idle .idle-title {
        font-size: 1.7rem;
      }
      ha-card.idle .idle-sub {
        font-size: 1.1rem;
      }
      ha-card.idle .idle-chips {
        gap: 10px;
        margin-top: 14px;
      }
      ha-card.idle .chip {
        font-size: 0.95rem;
        padding: 7px 16px 7px 11px;
      }
      ha-card.idle .chip ha-icon {
        --mdc-icon-size: 18px;
      }
      .media {
        flex: 1.6 1 0;
      }
      .controls {
        display: flex;
        flex-direction: column;
        gap: 14px;
        flex: 1 1 0;
        max-width: 380px;
      }
    }
    header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
    }
    .name {
      font-size: 1.15rem;
      font-weight: 600;
      color: var(--primary-text-color);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      color: var(--secondary-text-color);
      flex-shrink: 0;
    }
    .status.err {
      color: var(--error-color);
    }
    .timer {
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      color: var(--primary-text-color);
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--primary-color);
      animation: pulse 1s ease-in-out infinite;
    }
    @keyframes pulse {
      50% {
        opacity: 0.3;
      }
    }
    .connecting {
      position: absolute;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      background: rgba(0, 0, 0, 0.45);
      border-radius: 12px;
      color: #fff;
      font-weight: 600;
    }
    .spinner {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 4px solid rgba(255, 255, 255, 0.3);
      border-top-color: #fff;
      animation: spin 0.9s linear infinite;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .spinner,
      .dot {
        animation: none;
      }
    }
    .frame {
      position: absolute;
      inset: 0;
      background: var(--secondary-background-color);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: var(--secondary-text-color);
    }
    .frame.err {
      color: var(--error-color);
    }
    .frame ha-icon {
      --mdc-icon-size: 40px;
    }
    .actions {
      display: flex;
      gap: 16px;
      justify-content: center;
      flex-wrap: wrap;
    }
    .circle {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      border: none;
      background: none;
      cursor: pointer;
      color: var(--primary-text-color);
      font: inherit;
      min-width: 64px;
    }
    .circle ha-icon {
      --mdc-icon-size: 28px;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
    }
    .circle small {
      font-size: 0.78rem;
      color: var(--secondary-text-color);
    }
    .circle[disabled] {
      cursor: not-allowed;
      opacity: 0.5;
    }
    .circle.accept ha-icon {
      background: var(--success-color, #2e7d32);
      color: #fff;
    }
    .circle.reject ha-icon {
      background: var(--error-color, #c62828);
      color: #fff;
    }
    .circle.mic-on ha-icon {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
  `,p([f({attribute:!1})],g.prototype,"hass",2),p([_()],g.prototype,"_config",2),p([_()],g.prototype,"_muted",2),p([_()],g.prototype,"_micActive",2),p([_()],g.prototype,"_micPerm",2),p([_()],g.prototype,"_openStatus",2),p([_()],g.prototype,"_now",2),p([_()],g.prototype,"_errDismissed",2),g=p([R("eg-intercom-call-card")],g);window.customCards=window.customCards||[];window.customCards.push({type:"eg-intercom-call-card",name:"\u042D\u0413 \u0414\u043E\u043C\u043E\u0444\u043E\u043D \u2014 \u042D\u043A\u0440\u0430\u043D \u0432\u044B\u0437\u043E\u0432\u0430",description:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432 \u0438 \u0440\u0430\u0437\u0433\u043E\u0432\u043E\u0440 \u0441 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u043E\u043C: \u0432\u0438\u0434\u0435\u043E+\u0437\u0432\u0443\u043A, \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C, \u043F\u0440\u0438\u043D\u044F\u0442\u044C/\u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C, \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D. \u041E\u0434\u043D\u0430 \u043A\u0430\u0440\u0442\u0430 \u043D\u0430 \u0432\u0441\u0435 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u044B.",preview:!1});export{g as EgIntercomCallCard};
