/* eg-intercom-call-card — собранный бандл. Источник: frontend/src/. Не редактировать вручную. */
var Ie=Object.defineProperty;var We=Object.getOwnPropertyDescriptor;var c=(r,e,t,i)=>{for(var s=i>1?void 0:i?We(e,t):e,n=r.length-1,o;n>=0;n--)(o=r[n])&&(s=(i?o(e,t,s):o(s))||s);return i&&s&&Ie(e,t,s),s};var G=globalThis,X=G.ShadowRoot&&(G.ShadyCSS===void 0||G.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,re=Symbol(),fe=new WeakMap,D=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==re)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(X&&e===void 0){let i=t!==void 0&&t.length===1;i&&(e=fe.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&fe.set(t,e))}return e}toString(){return this.cssText}},ve=r=>new D(typeof r=="string"?r:r+"",void 0,re),b=(r,...e)=>{let t=r.length===1?r[0]:e.reduce((i,s,n)=>i+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s)+r[n+1],r[0]);return new D(t,r,re)},_e=(r,e)=>{if(X)r.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let i=document.createElement("style"),s=G.litNonce;s!==void 0&&i.setAttribute("nonce",s),i.textContent=t.cssText,r.appendChild(i)}},ne=X?r=>r:r=>r instanceof CSSStyleSheet?(e=>{let t="";for(let i of e.cssRules)t+=i.cssText;return ve(t)})(r):r;var{is:Ke,defineProperty:Fe,getOwnPropertyDescriptor:Ge,getOwnPropertyNames:Xe,getOwnPropertySymbols:Ye,getPrototypeOf:Je}=Object,Y=globalThis,be=Y.trustedTypes,Ze=be?be.emptyScript:"",Qe=Y.reactiveElementPolyfillSupport,L=(r,e)=>r,j={toAttribute(r,e){switch(e){case Boolean:r=r?Ze:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,e){let t=r;switch(e){case Boolean:t=r!==null;break;case Number:t=r===null?null:Number(r);break;case Object:case Array:try{t=JSON.parse(r)}catch{t=null}}return t}},J=(r,e)=>!Ke(r,e),xe={attribute:!0,type:String,converter:j,reflect:!1,useDefault:!1,hasChanged:J};Symbol.metadata??=Symbol("metadata"),Y.litPropertyMetadata??=new WeakMap;var k=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=xe){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let i=Symbol(),s=this.getPropertyDescriptor(e,i,t);s!==void 0&&Fe(this.prototype,e,s)}}static getPropertyDescriptor(e,t,i){let{get:s,set:n}=Ge(this.prototype,e)??{get(){return this[t]},set(o){this[t]=o}};return{get:s,set(o){let p=s?.call(this);n?.call(this,o),this.requestUpdate(e,p,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??xe}static _$Ei(){if(this.hasOwnProperty(L("elementProperties")))return;let e=Je(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(L("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(L("properties"))){let t=this.properties,i=[...Xe(t),...Ye(t)];for(let s of i)this.createProperty(s,t[s])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[i,s]of t)this.elementProperties.set(i,s)}this._$Eh=new Map;for(let[t,i]of this.elementProperties){let s=this._$Eu(t,i);s!==void 0&&this._$Eh.set(s,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let s of i)t.unshift(ne(s))}else e!==void 0&&t.push(ne(e));return t}static _$Eu(e,t){let i=t.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return _e(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){let i=this.constructor.elementProperties.get(e),s=this.constructor._$Eu(e,i);if(s!==void 0&&i.reflect===!0){let n=(i.converter?.toAttribute!==void 0?i.converter:j).toAttribute(t,i.type);this._$Em=e,n==null?this.removeAttribute(s):this.setAttribute(s,n),this._$Em=null}}_$AK(e,t){let i=this.constructor,s=i._$Eh.get(e);if(s!==void 0&&this._$Em!==s){let n=i.getPropertyOptions(s),o=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:j;this._$Em=s;let p=o.fromAttribute(t,n.type);this[s]=p??this._$Ej?.get(s)??p,this._$Em=null}}requestUpdate(e,t,i,s=!1,n){if(e!==void 0){let o=this.constructor;if(s===!1&&(n=this[e]),i??=o.getPropertyOptions(e),!((i.hasChanged??J)(n,t)||i.useDefault&&i.reflect&&n===this._$Ej?.get(e)&&!this.hasAttribute(o._$Eu(e,i))))return;this.C(e,t,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:s,wrapped:n},o){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,o??t??this[e]),n!==!0||o!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),s===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[s,n]of this._$Ep)this[s]=n;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[s,n]of i){let{wrapped:o}=n,p=this[s];o!==!0||this._$AL.has(s)||p===void 0||this.C(s,void 0,n,p)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(t)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};k.elementStyles=[],k.shadowRootOptions={mode:"open"},k[L("elementProperties")]=new Map,k[L("finalized")]=new Map,Qe?.({ReactiveElement:k}),(Y.reactiveElementVersions??=[]).push("2.1.2");var he=globalThis,ye=r=>r,Z=he.trustedTypes,we=Z?Z.createPolicy("lit-html",{createHTML:r=>r}):void 0,Pe="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,Te="?"+P,et=`<${Te}>`,C=document,q=()=>C.createComment(""),V=r=>r===null||typeof r!="object"&&typeof r!="function",ue=Array.isArray,tt=r=>ue(r)||typeof r?.[Symbol.iterator]=="function",oe=`[ 	
\f\r]`,B=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,$e=/-->/g,Ae=/>/g,T=RegExp(`>|${oe}(?:([^\\s"'>=/]+)(${oe}*=${oe}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ke=/'/g,Se=/"/g,Ee=/^(?:script|style|textarea|title)$/i,me=r=>(e,...t)=>({_$litType$:r,strings:e,values:t}),l=me(1),St=me(2),Mt=me(3),S=Symbol.for("lit-noChange"),d=Symbol.for("lit-nothing"),Me=new WeakMap,E=C.createTreeWalker(C,129);function Ce(r,e){if(!ue(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return we!==void 0?we.createHTML(e):e}var it=(r,e)=>{let t=r.length-1,i=[],s,n=e===2?"<svg>":e===3?"<math>":"",o=B;for(let p=0;p<t;p++){let a=r[p],m,g,h=-1,y=0;for(;y<a.length&&(o.lastIndex=y,g=o.exec(a),g!==null);)y=o.lastIndex,o===B?g[1]==="!--"?o=$e:g[1]!==void 0?o=Ae:g[2]!==void 0?(Ee.test(g[2])&&(s=RegExp("</"+g[2],"g")),o=T):g[3]!==void 0&&(o=T):o===T?g[0]===">"?(o=s??B,h=-1):g[1]===void 0?h=-2:(h=o.lastIndex-g[2].length,m=g[1],o=g[3]===void 0?T:g[3]==='"'?Se:ke):o===Se||o===ke?o=T:o===$e||o===Ae?o=B:(o=T,s=void 0);let w=o===T&&r[p+1].startsWith("/>")?" ":"";n+=o===B?a+et:h>=0?(i.push(m),a.slice(0,h)+Pe+a.slice(h)+P+w):a+P+(h===-2?p:w)}return[Ce(r,n+(r[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},I=class r{constructor({strings:e,_$litType$:t},i){let s;this.parts=[];let n=0,o=0,p=e.length-1,a=this.parts,[m,g]=it(e,t);if(this.el=r.createElement(m,i),E.currentNode=this.el.content,t===2||t===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(s=E.nextNode())!==null&&a.length<p;){if(s.nodeType===1){if(s.hasAttributes())for(let h of s.getAttributeNames())if(h.endsWith(Pe)){let y=g[o++],w=s.getAttribute(h).split(P),F=/([.?@])?(.*)/.exec(y);a.push({type:1,index:n,name:F[2],strings:w,ctor:F[1]==="."?ce:F[1]==="?"?le:F[1]==="@"?de:O}),s.removeAttribute(h)}else h.startsWith(P)&&(a.push({type:6,index:n}),s.removeAttribute(h));if(Ee.test(s.tagName)){let h=s.textContent.split(P),y=h.length-1;if(y>0){s.textContent=Z?Z.emptyScript:"";for(let w=0;w<y;w++)s.append(h[w],q()),E.nextNode(),a.push({type:2,index:++n});s.append(h[y],q())}}}else if(s.nodeType===8)if(s.data===Te)a.push({type:2,index:n});else{let h=-1;for(;(h=s.data.indexOf(P,h+1))!==-1;)a.push({type:7,index:n}),h+=P.length-1}n++}}static createElement(e,t){let i=C.createElement("template");return i.innerHTML=e,i}};function H(r,e,t=r,i){if(e===S)return e;let s=i!==void 0?t._$Co?.[i]:t._$Cl,n=V(e)?void 0:e._$litDirective$;return s?.constructor!==n&&(s?._$AO?.(!1),n===void 0?s=void 0:(s=new n(r),s._$AT(r,t,i)),i!==void 0?(t._$Co??=[])[i]=s:t._$Cl=s),s!==void 0&&(e=H(r,s._$AS(r,e.values),s,i)),e}var ae=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:i}=this._$AD,s=(e?.creationScope??C).importNode(t,!0);E.currentNode=s;let n=E.nextNode(),o=0,p=0,a=i[0];for(;a!==void 0;){if(o===a.index){let m;a.type===2?m=new W(n,n.nextSibling,this,e):a.type===1?m=new a.ctor(n,a.name,a.strings,this,e):a.type===6&&(m=new pe(n,this,e)),this._$AV.push(m),a=i[++p]}o!==a?.index&&(n=E.nextNode(),o++)}return E.currentNode=C,s}p(e){let t=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}},W=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,s){this.type=2,this._$AH=d,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=H(this,e,t),V(e)?e===d||e==null||e===""?(this._$AH!==d&&this._$AR(),this._$AH=d):e!==this._$AH&&e!==S&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):tt(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==d&&V(this._$AH)?this._$AA.nextSibling.data=e:this.T(C.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:i}=e,s=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=I.createElement(Ce(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(t);else{let n=new ae(s,this),o=n.u(this.options);n.p(t),this.T(o),this._$AH=n}}_$AC(e){let t=Me.get(e.strings);return t===void 0&&Me.set(e.strings,t=new I(e)),t}k(e){ue(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,i,s=0;for(let n of e)s===t.length?t.push(i=new r(this.O(q()),this.O(q()),this,this.options)):i=t[s],i._$AI(n),s++;s<t.length&&(this._$AR(i&&i._$AB.nextSibling,s),t.length=s)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let i=ye(e).nextSibling;ye(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},O=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,s,n){this.type=1,this._$AH=d,this._$AN=void 0,this.element=e,this.name=t,this._$AM=s,this.options=n,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=d}_$AI(e,t=this,i,s){let n=this.strings,o=!1;if(n===void 0)e=H(this,e,t,0),o=!V(e)||e!==this._$AH&&e!==S,o&&(this._$AH=e);else{let p=e,a,m;for(e=n[0],a=0;a<n.length-1;a++)m=H(this,p[i+a],t,a),m===S&&(m=this._$AH[a]),o||=!V(m)||m!==this._$AH[a],m===d?e=d:e!==d&&(e+=(m??"")+n[a+1]),this._$AH[a]=m}o&&!s&&this.j(e)}j(e){e===d?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},ce=class extends O{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===d?void 0:e}},le=class extends O{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==d)}},de=class extends O{constructor(e,t,i,s,n){super(e,t,i,s,n),this.type=5}_$AI(e,t=this){if((e=H(this,e,t,0)??d)===S)return;let i=this._$AH,s=e===d&&i!==d||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,n=e!==d&&(i===d||s);s&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},pe=class{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){H(this,e)}};var st=he.litHtmlPolyfillSupport;st?.(I,W),(he.litHtmlVersions??=[]).push("3.3.3");var Re=(r,e,t)=>{let i=t?.renderBefore??e,s=i._$litPart$;if(s===void 0){let n=t?.renderBefore??null;i._$litPart$=s=new W(e.insertBefore(q(),n),n,void 0,t??{})}return s._$AI(r),s};var ge=globalThis,_=class extends k{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Re(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};_._$litElement$=!0,_.finalized=!0,ge.litElementHydrateSupport?.({LitElement:_});var rt=ge.litElementPolyfillSupport;rt?.({LitElement:_});(ge.litElementVersions??=[]).push("4.2.2");var A=r=>(e,t)=>{t!==void 0?t.addInitializer(()=>{customElements.define(r,e)}):customElements.define(r,e)};var nt={attribute:!0,type:String,converter:j,reflect:!1,hasChanged:J},ot=(r=nt,e,t)=>{let{kind:i,metadata:s}=t,n=globalThis.litPropertyMetadata.get(s);if(n===void 0&&globalThis.litPropertyMetadata.set(s,n=new Map),i==="setter"&&((r=Object.create(r)).wrapped=!0),n.set(t.name,r),i==="accessor"){let{name:o}=t;return{set(p){let a=e.get.call(this);e.set.call(this,p),this.requestUpdate(o,a,r,!0,p)},init(p){return p!==void 0&&this.C(o,void 0,r,p),p}}}if(i==="setter"){let{name:o}=t;return function(p){let a=this[o];e.call(this,p),this.requestUpdate(o,a,r,!0,p)}}throw Error("Unsupported decorator location: "+i)};function u(r){return(e,t)=>typeof t=="object"?ot(r,e,t):((i,s,n)=>{let o=s.hasOwnProperty(n);return s.constructor.createProperty(n,i),o?Object.getOwnPropertyDescriptor(s,n):void 0})(r,e,t)}function f(r){return u({...r,state:!0,attribute:!1})}var at=new Set(["idle","ringing","connecting","active","ended","error"]);function He(r){return r&&at.has(r)?r:"idle"}var U={visible:!1,video:"none",actions:[],showOpen:!1,showTimer:!1,showAnswerWindow:!1,busy:!1,isError:!1};function Oe(r){switch(r){case"ringing":return{...U,visible:!0,video:"doorbell",actions:["reject","accept"],showOpen:!0,showAnswerWindow:!0};case"connecting":return{...U,visible:!0,video:"doorbell",actions:["cancel","connecting"],showOpen:!0,busy:!0};case"active":return{...U,visible:!0,video:"call",actions:["mic","sound","hangup"],showOpen:!0,showTimer:!0};case"error":return{...U,visible:!0,video:"none",actions:["retry","hangup"],showOpen:!0,isError:!0};case"ended":return{...U,visible:!0,video:"call",actions:["close"],showOpen:!0};case"idle":default:return{...U}}}var Ue={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},te=r=>(...e)=>({_$litDirective$:r,values:e}),ee=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,i){this._$Ct=e,this._$AM=t,this._$Ci=i}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}};var R=class extends ee{constructor(e){if(super(e),this.it=d,e.type!==Ue.CHILD)throw Error(this.constructor.directiveName+"() can only be used in child bindings")}render(e){if(e===d||e==null)return this._t=void 0,this.it=e;if(e===S)return e;if(typeof e!="string")throw Error(this.constructor.directiveName+"() called with a non-string value");if(e===this.it)return this._t;this.it=e;let t=[e];return t.raw=t,this._t={_$litType$:this.constructor.resultType,strings:t,values:[]}}};R.directiveName="unsafeHTML",R.resultType=1;var vi=te(R);var K=class extends R{};K.directiveName="unsafeSVG",K.resultType=2;var Ne=te(K);var ct={"key-round":'<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',lock:'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',"lock-open":'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',phone:'<path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"/>',"phone-off":'<path d="M10.1 13.9a14 14 0 0 0 3.732 2.668 1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2 18 18 0 0 1-12.728-5.272"/><path d="M22 2 2 22"/><path d="M4.76 13.582A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 .244.473"/>',mic:'<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',"mic-off":'<path d="M12 19v3"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M16.95 16.95A7 7 0 0 1 5 12v-2"/><path d="M18.89 13.23A7 7 0 0 0 19 12v-2"/><path d="m2 2 20 20"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/>',"volume-2":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',"volume-x":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/>',x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',timer:'<line x1="10" x2="14" y1="2" y2="2"/><line x1="12" x2="15" y1="14" y2="11"/><circle cx="12" cy="14" r="8"/>',"refresh-cw":'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',"door-open":'<path d="M11 20H2"/><path d="M11 4.562v16.157a1 1 0 0 0 1.242.97L19 20V5.562a2 2 0 0 0-1.515-1.94l-4-1A2 2 0 0 0 11 4.561z"/><path d="M11 4H8a2 2 0 0 0-2 2v14"/><path d="M14 12h.01"/><path d="M22 20h-3"/>',"video-off":'<path d="M10.66 6H14a2 2 0 0 1 2 2v2.5l5.248-3.062A.5.5 0 0 1 22 7.87v8.196"/><path d="M16 16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2"/><path d="m2 2 20 20"/>',"wifi-off":'<path d="M12 20h.01"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/><path d="M5 12.859a10 10 0 0 1 5.17-2.69"/><path d="M19 12.859a10 10 0 0 0-2.007-1.523"/><path d="M2 8.82a15 15 0 0 1 4.177-2.643"/><path d="M22 8.82a15 15 0 0 0-11.288-3.764"/><path d="m2 2 20 20"/>',"circle-check":'<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',"chevron-right":'<path d="m9 18 6-6-6-6"/>',"bell-ring":'<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M22 8c0-2.3-.8-4.3-2-6"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/>',"loader-circle":'<path d="M21 12a9 9 0 1 1-6.219-8.56"/>'},N=class extends _{constructor(){super(...arguments);this.name=""}render(){let t=ct[this.name]??"";return l`<svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >${Ne(t)}</svg>`}};N.styles=b`
    :host {
      display: inline-flex;
      width: var(--eg-icon-size, 24px);
      height: var(--eg-icon-size, 24px);
      line-height: 0;
      flex: none;
    }
    svg {
      width: 100%;
      height: 100%;
      display: block;
    }
  `,c([u()],N.prototype,"name",2),N=c([A("eg-icon")],N);function ze(r,e){if(r==="call")return e.camera;if(r==="doorbell")return e.doorbell_camera??e.camera}var M=class extends _{constructor(){super(...arguments);this.muted=!1;this._provider="pending"}connectedCallback(){super.connectedCallback(),this._resolveProvider()}async _resolveProvider(){if(customElements.get("ha-camera-stream")){this._provider="ha";return}try{await window.loadCardHelpers?.()}catch{}customElements.get("ha-camera-stream")?this._provider="ha":customElements.get("webrtc-camera")?this._provider="webrtc":this._provider="none"}updated(t){this._provider==="webrtc"&&this._syncWebrtc(t)}_syncWebrtc(t){let i=this.renderRoot.querySelector("#webrtc-host");if(!(!i||!this.entity||!this.hass))if(t.has("entity")||t.has("_provider")||t.has("muted")||!this._webrtcEl){i.replaceChildren();let s=document.createElement("webrtc-camera");s.setConfig({entity:this.entity,muted:this.muted}),s.hass=this.hass,i.appendChild(s),this._webrtcEl=s}else this._webrtcEl.hass=this.hass}render(){if(!this.entity||!this.hass)return this._frame("video-off","\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u0438\u0434\u0435\u043E");let t=this.hass.states[this.entity];if(!t)return this._frame("video-off","\u041A\u0430\u043C\u0435\u0440\u0430 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u0430");switch(this._provider){case"pending":return this._frame("video-off","\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0432\u0438\u0434\u0435\u043E\u2026");case"ha":return l`
          <ha-camera-stream
            .hass=${this.hass}
            .stateObj=${t}
            .muted=${this.muted}
          ></ha-camera-stream>
        `;case"webrtc":return l`<div id="webrtc-host"></div>`;default:return this._frame("video-off","\u0412\u0438\u0434\u0435\u043E\u043F\u043B\u0435\u0435\u0440 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D \u2014 \u043E\u0431\u043D\u043E\u0432\u0438\u0442\u0435 HA \u0438\u043B\u0438 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0435 advanced-camera-card")}}_frame(t,i){return l`
      <div class="frame" role="img" aria-label=${i}>
        <eg-icon name=${t}></eg-icon>
        <span>${i}</span>
      </div>
      ${d}
    `}};M.styles=b`
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
    .frame eg-icon {
      --eg-icon-size: 40px;
    }
    .frame span {
      font-size: 0.85rem;
    }
  `,c([u({attribute:!1})],M.prototype,"hass",2),c([u()],M.prototype,"entity",2),c([u({type:Boolean})],M.prototype,"muted",2),c([f()],M.prototype,"_provider",2),M=c([A("eg-call-video")],M);var z=b`
  :host {
    --eg-primary: var(--primary-color, #03a9f4);
    --eg-success: var(--success-color, #4caf50);
    --eg-error: var(--error-color, #ef5350);
    --eg-warning: var(--warning-color, #ffb300);
    --eg-text: var(--primary-text-color, #e8e8e8);
    --eg-text-2: var(--secondary-text-color, #a6a6a6);
    --eg-text-3: var(--disabled-text-color, #787878);
    --eg-elevated: var(--secondary-background-color, #2a2a2a);
    --eg-card: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --eg-divider: var(--divider-color, #2e2e2e);
    --eg-on-fill: var(--text-primary-color, #ffffff);
    --eg-scrim: rgba(0, 0, 0, 0.72);
    --eg-r-card: 16px;
    --eg-r-md: 12px;
    --eg-r-full: 999px;
    --eg-mono: "Roboto Mono", ui-monospace, monospace;
    /* Тинты бейджей/баннеров = роль-цвет @ ~18% (эквивалент alpha 2E/1A из макета). */
    --eg-primary-bg: color-mix(in srgb, var(--eg-primary) 18%, transparent);
    --eg-success-bg: color-mix(in srgb, var(--eg-success) 18%, transparent);
    --eg-error-bg: color-mix(in srgb, var(--eg-error) 18%, transparent);
    --eg-warning-bg: color-mix(in srgb, var(--eg-warning) 18%, transparent);
  }
`,lt={idle:"var(--eg-text-2)",ringing:"var(--eg-warning)",connecting:"var(--eg-primary)",active:"var(--eg-success)",ended:"var(--eg-text-2)",error:"var(--eg-error)"};function De(r){return lt[r]??"var(--eg-text-2)"}function dt(r){switch(r){case"camera_off":return"placeholder-camera";case"connection_lost":return"placeholder-connection";case"ended":return"video-dimmed";default:return"video"}}var x=class extends _{constructor(){super(...arguments);this.muted=!1;this.live=!1;this.soundOff=!1;this.timestamp="";this.stageState="live";this.audioBlocked=!1;this._unmute=()=>{this.dispatchEvent(new CustomEvent("unmute",{bubbles:!0,composed:!0}))}}render(){let t=dt(this.stageState);return t==="placeholder-camera"?this._placeholder("video-off","muted","\u0412\u0438\u0434\u0435\u043E \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u043E","\u0410\u0443\u0434\u0438\u043E\u0432\u044B\u0437\u043E\u0432 \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0430\u0435\u0442\u0441\u044F"):t==="placeholder-connection"?this._placeholder("wifi-off","err","\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435 \u043F\u0440\u0435\u0440\u0432\u0430\u043D\u043E","\u041F\u0440\u043E\u0431\u0443\u0435\u043C \u0432\u043E\u0441\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C\u2026"):l`
      <eg-call-video .hass=${this.hass} .entity=${this.entity} .muted=${this.muted}></eg-call-video>
      ${t==="video-dimmed"?l`<div class="dim" aria-hidden="true"></div>`:d}
      <div class="top">
        ${this.live?l`<span class="live"><span class="live-dot" aria-hidden="true"></span>LIVE</span>`:d}
        ${this.soundOff?l`<span class="chip"><eg-icon name="volume-x"></eg-icon>Звук выкл.</span>`:d}
      </div>
      ${this.timestamp&&!this.audioBlocked?l`<span class="ts">${this.timestamp}</span>`:d}
      ${this.audioBlocked?l`
            <button class="tap" @click=${this._unmute} aria-label="Включить звук"></button>
            <span class="cta" aria-hidden="true">
              <eg-icon name="volume-x"></eg-icon>Нажмите, чтобы включить звук
            </span>
          `:d}
    `}_placeholder(t,i,s,n){return l`
      <div class="fallback ${i}" role="img" aria-label=${s}>
        <eg-icon name=${t}></eg-icon>
        <span class="fb-title">${s}</span>
        <span class="fb-sub">${n}</span>
      </div>
    `}};x.styles=[z,b`
      :host {
        position: absolute;
        inset: 0;
        display: block;
      }
      eg-call-video {
        position: absolute;
        inset: 0;
      }
      .dim {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
      }
      /* верхний ряд оверлеев: LIVE (слева) + чип звука (справа) */
      .top {
        position: absolute;
        top: 12px;
        left: 12px;
        right: 12px;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        pointer-events: none;
      }
      .live {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 9px;
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.04em;
      }
      .live-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #fff;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px;
        border-radius: var(--eg-r-full);
        background: rgba(0, 0, 0, 0.63);
        color: #fff;
        font-size: 11px;
      }
      .chip eg-icon {
        --eg-icon-size: 14px;
      }
      .ts {
        position: absolute;
        left: 12px;
        bottom: 12px;
        font-size: 10px;
        color: rgba(255, 255, 255, 0.69);
        font-variant-numeric: tabular-nums;
        pointer-events: none;
      }
      /* CTA «включить звук» + прозрачный tap-слой поверх всего видео */
      .tap {
        position: absolute;
        inset: 0;
        border: none;
        background: transparent;
        cursor: pointer;
        z-index: 2;
      }
      /* CTA — в НИЖНЕЙ части видео (не перекрывает лицо звонящего), UX §8/§13 */
      .cta {
        position: absolute;
        left: 50%;
        bottom: 16px;
        transform: translateX(-50%);
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 18px;
        border-radius: var(--eg-r-full);
        background: var(--eg-scrim);
        color: #fff;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
        z-index: 3;
        pointer-events: none;
      }
      .cta eg-icon {
        --eg-icon-size: 18px;
      }
      /* плейсхолдеры (камера недоступна / связь прервана) */
      .fallback {
        position: absolute;
        inset: 0;
        background: var(--eg-card);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-align: center;
        padding: 12px;
        box-sizing: border-box;
      }
      .fallback eg-icon {
        --eg-icon-size: 36px;
        color: var(--eg-text-3);
      }
      .fallback.err eg-icon {
        color: var(--eg-error);
      }
      .fb-title {
        font-size: 15px;
        color: var(--eg-text);
      }
      .fb-sub {
        font-size: 12px;
        color: var(--eg-text-2);
      }
    `],c([u({attribute:!1})],x.prototype,"hass",2),c([u()],x.prototype,"entity",2),c([u({type:Boolean})],x.prototype,"muted",2),c([u({type:Boolean})],x.prototype,"live",2),c([u({type:Boolean})],x.prototype,"soundOff",2),c([u()],x.prototype,"timestamp",2),c([u()],x.prototype,"stageState",2),c([u({type:Boolean})],x.prototype,"audioBlocked",2),x=c([A("eg-call-stage")],x);function Le(r){return r<0?0:r>1?1:r}function pt(r,e,t,i){let s=Math.max(1,t-i);return Le((r-e-i/2)/s)}function ht(r,e){return Le(r/Math.max(1,e))}var ut=.92,mt=800,gt=68,$=class extends _{constructor(){super(...arguments);this.mode="hold";this.disabled=!1;this.label="\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C";this.status="idle";this._progress=0;this._arming=!1;this._raf=0;this._holdStart=0;this._trackRect=null;this._holdTick=()=>{if(this._progress=ht(performance.now()-this._holdStart,mt),this._progress>=1){this._reset(),this._fireOpen();return}this._raf=requestAnimationFrame(this._holdTick)};this._onHoldDown=t=>{this.disabled||(t.target.setPointerCapture?.(t.pointerId),this._arming=!0,this._holdStart=performance.now(),this._raf=requestAnimationFrame(this._holdTick))};this._onHoldUp=()=>{this._progress<1&&this._reset()};this._onSlideDown=t=>{if(this.disabled)return;let i=t.currentTarget.closest(".track");this._trackRect=i?.getBoundingClientRect()??null,t.target.setPointerCapture?.(t.pointerId),this._arming=!0};this._onSlideMove=t=>{!this._arming||!this._trackRect||(this._progress=pt(t.clientX,this._trackRect.left,this._trackRect.width,gt))};this._onSlideUp=()=>{this._progress>=ut?(this._reset(),this._fireOpen()):this._reset()};this._onTap=()=>{this.disabled||this._fireOpen()}}_fireOpen(){this.dispatchEvent(new CustomEvent("open",{bubbles:!0,composed:!0}))}_reset(){this._raf&&cancelAnimationFrame(this._raf),this._raf=0,this._arming=!1,this._progress=0,this._trackRect=null}render(){let t=this.mode==="tap"?this._renderTap():this.mode==="slide"?this._renderSlide():this._renderHold();return l`
      <div class="wrap" style="--eg-prog:${this._vp()}">
        ${t}
        ${this._caption()}
      </div>
    `}_caption(){let t="",i="";if(this.status==="opened")t="\u0414\u0432\u0435\u0440\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u0430",i="st-opened";else if(this.status==="error")t="\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u044C \xB7 \u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",i="st-error";else if(this.status==="opening")t="\u041E\u0442\u043A\u0440\u044B\u0432\u0430\u044E\u2026";else if(this.mode==="slide")t="\u0421\u0434\u0432\u0438\u043D\u044C\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C";else return l``;return l`<span class="caption ${i}">${t}</span>`}_labelText(){return this.status==="opened"?"\u041E\u0442\u043A\u0440\u044B\u0442\u043E":this.mode==="slide"?"\u041E\u0442\u043A\u0440\u044B\u0442\u044C":"\u0423\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0439\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C"}_barIcon(){return this.status==="opened"?"lock-open":"key-round"}_knobIcon(){return"key-round"}_vp(){return this.status==="opened"?1:this._progress}_statusClass(){return this.status==="opened"?"st-opened":this.status==="error"?"st-error":""}_renderTap(){return l`
      <button class="pill tap ${this._statusClass()}" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this.label}>
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `}_renderHold(){return l`
      <button
        class="pill hold ${this._arming?"arming":""} ${this._statusClass()}"
        ?disabled=${this.disabled}
        aria-label="${this.label} — удерживайте"
        @pointerdown=${this._onHoldDown}
        @pointerup=${this._onHoldUp}
        @pointercancel=${this._onHoldUp}
        @pointerleave=${this._onHoldUp}
      >
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `}_renderSlide(){return l`
      <div
        class="track ${this._statusClass()} ${this._arming?"dragging":""}"
        role="slider"
        aria-label=${this.label}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(this._vp()*100)}
      >
        <eg-icon class="lock-under" name="lock"></eg-icon>
        <eg-icon class="end" name="lock-open"></eg-icon>
        <div class="fill"></div>
        <span class="label">${this._labelText()}</span>
        <div
          class="knob ${this.disabled?"off":""}"
          @pointerdown=${this._onSlideDown}
          @pointermove=${this._onSlideMove}
          @pointerup=${this._onSlideUp}
          @pointercancel=${this._onSlideUp}
        >
          <eg-icon name=${this._knobIcon()}></eg-icon>
        </div>
      </div>
    `}};$.styles=[z,b`
      :host {
        display: block;
      }
      .wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
        align-items: center;
        width: 100%;
      }
      /* ---- общая заливка-прогресс ---- */
      .fill {
        position: absolute;
        inset: 0 auto 0 0;
        width: calc(var(--eg-prog, 0) * 100%);
        background: var(--eg-primary);
        opacity: 0.15;
        transition: width 0.2s ease;
      }
      /* ---- slide: трек 300×80 (макет: фиксированный, центрирован — не на всю ширину) ---- */
      .track {
        position: relative;
        width: 300px;
        max-width: 100%;
        height: 80px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        touch-action: none;
        user-select: none;
      }
      /* в покое заливки нет (иначе «залипло»); появляется только при перетаскивании */
      .track .fill {
        width: 0;
      }
      /* при drag правый край заливки строго = центр ключа (не обгоняет) */
      .track.dragging .fill {
        width: calc(40px + var(--eg-prog, 0) * (100% - 80px));
        transition: none;
      }
      /* закрытый замок под ключом (проявляется при отъезде): иконка 20, центр под ключом */
      .lock-under {
        position: absolute;
        left: 30px;
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: 20px;
        color: var(--eg-text-3);
        z-index: 0;
      }
      /* торец: открытый замок (макет: иконка 20, центр 28px от правого края) */
      .end {
        position: absolute;
        right: 18px;
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: 20px;
        color: var(--eg-text-3);
        z-index: 0;
      }
      .track .label {
        position: relative;
        z-index: 1;
        font-size: 17px;
        font-weight: 600;
        color: var(--eg-text);
      }
      .knob {
        position: absolute;
        top: 6px;
        left: calc(6px + var(--eg-prog, 0) * (100% - 80px));
        width: 68px;
        height: 68px;
        border-radius: 50%;
        background: var(--eg-primary);
        color: var(--eg-on-fill);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        touch-action: none;
        z-index: 2;
        --eg-icon-size: 28px;
        transition: left 0.18s ease;
      }
      .track.dragging .knob {
        transition: none;
        cursor: grabbing;
      }
      .knob.off {
        opacity: 0.5;
      }
      /* slide success: зелёный трек + «Открыто» + ключ справа */
      .track.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .track.st-opened .label {
        color: var(--eg-on-fill);
      }
      .track.st-opened .knob {
        background: var(--eg-success);
      }
      /* success: ключ-knob уехал вправо и накрыл торец — торец прячем */
      .track.st-opened .end {
        display: none;
      }
      /* ---- hold/tap: outlined-пилюля, контент неподвижен, заливка бежит ---- */
      .pill {
        position: relative;
        width: 100%;
        min-height: 64px;
        border-radius: var(--eg-r-full);
        border: 2px solid var(--eg-primary);
        background: transparent;
        color: var(--eg-text);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        cursor: pointer;
        touch-action: none;
        user-select: none;
        font: inherit;
        padding: 0 16px;
      }
      .pill.arming .fill {
        transition: none;
      }
      .pill .fill {
        opacity: 0.2;
      }
      .pill .content {
        position: relative;
        z-index: 1;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 17px;
        font-weight: 600;
        --eg-icon-size: 24px;
      }
      .pill[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .pill.st-opened {
        border-color: var(--eg-success);
      }
      .pill.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .pill.st-opened .content {
        color: var(--eg-on-fill);
      }
      /* ---- подпись под контролом ---- */
      .caption {
        font-size: 12px;
        color: var(--eg-text-3);
        text-align: center;
      }
      .caption.st-opened {
        color: var(--eg-success);
      }
      .caption.st-error {
        color: var(--eg-error);
      }
      @media (prefers-reduced-motion: reduce) {
        .fill,
        .knob {
          transition: none;
        }
      }
    `],c([u()],$.prototype,"mode",2),c([u({type:Boolean})],$.prototype,"disabled",2),c([u()],$.prototype,"label",2),c([u()],$.prototype,"status",2),c([f()],$.prototype,"_progress",2),c([f()],$.prototype,"_arming",2),$=c([A("eg-open-control")],$);function je(r,e){return e&&r==="granted"}var ie=class{constructor(e,t=()=>{}){this._getConn=e;this._onChange=t;this.active=!1;this.lastError=""}async queryPermission(){try{return(await navigator.permissions?.query({name:"microphone"}))?.state??"unknown"}catch{return"unknown"}}get secure(){return typeof window<"u"&&window.isSecureContext===!0}async start(){if(this.active)return;let e=this._getConn();if(!e){this._fail("\u043D\u0435\u0442 \u0441\u0432\u044F\u0437\u0438 \u0441 Home Assistant");return}if(!navigator.mediaDevices?.getUserMedia){this._fail("\u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D (\u043D\u0443\u0436\u0435\u043D HTTPS-origin)");return}try{let t=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0}}),i=window.AudioContext||window.webkitAudioContext,s=new i,n=s.sampleRate,o=this._sub;(!o||o.sampleRate!==n)&&(o={handlerId:(await e.sendMessagePromise({type:"elektronny_gorod/intercom_uplink",sample_rate:n})).handler_id,sampleRate:n},this._sub=o);let p=o.handlerId,a=e.socket;await s.audioWorklet.addModule(this._workletUrl());let m=new AudioWorkletNode(s,"eg-pcm-int16",{numberOfOutputs:0});m.port.onmessage=h=>{let y=h.data,w=new Uint8Array(1+y.byteLength);w[0]=p,w.set(new Uint8Array(y.buffer),1),a.readyState===1&&a.send(w)};let g=s.createMediaStreamSource(t);g.connect(m),this._ctx={ac:s,stream:t,node:m,src:g},this.active=!0,this.lastError="",this._onChange()}catch(t){this._fail(t instanceof Error?t.message:String(t))}}stop(){let e=this._ctx;if(e){try{e.node.port.onmessage=null,e.node.disconnect(),e.src.disconnect()}catch{}try{e.stream.getTracks().forEach(t=>t.stop())}catch{}try{e.ac.close()}catch{}}if(this._ctx=void 0,this.active=!1,this._wUrl){try{URL.revokeObjectURL(this._wUrl)}catch{}this._wUrl=void 0}this._onChange()}_fail(e){this.lastError=e,this.stop()}_workletUrl(){if(this._wUrl)return this._wUrl;let e=`
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
      registerProcessor("eg-pcm-int16", EgPcmInt16);`;return this._wUrl=URL.createObjectURL(new Blob([e],{type:"application/javascript"})),this._wUrl}};var ft=new Set(["slide","hold","tap"]);function Be(r,e){return r&&ft.has(r)?r:e?"slide":"hold"}function qe(){return typeof window<"u"&&typeof window.matchMedia=="function"&&window.matchMedia("(pointer: coarse)").matches}var vt={ringing:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432",connecting:"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026",active:"\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440",ended:"\u0412\u044B\u0437\u043E\u0432 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D",error:"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430"},se=new Set(["ringing","connecting","active","error"]),_t=6e3,bt=3e3,Ve=3e4,xt=2500,v=class extends _{constructor(){super(...arguments);this._config={};this._muted=!1;this._audioBlocked=!1;this._micActive=!1;this._micPerm="unknown";this._openStatus="idle";this._now=Date.now();this._ringingSince=0;this._errDismissed=new Set;this._endedEntity="";this._endedDuration="";this._doorbells=[];this._openAction="hold";this._prevKey="";this._prevPhases=new Map;this._mic=new ie(()=>this.hass?.connection,()=>{this._micActive=this._mic.active,this.requestUpdate()});this._clearEnded=()=>{this._endedHide&&(clearTimeout(this._endedHide),this._endedHide=void 0),this._endedEntity="",this.requestUpdate()};this._unmute=()=>{this._muted=!1,this._audioBlocked=!1};this._answer=()=>{this.hass?.callService("elektronny_gorod","answer")};this._hangup=()=>{this.hass?.callService("elektronny_gorod","hangup")};this._toggleMute=()=>{this._muted=!this._muted};this._toggleMic=async()=>{this._mic.active?this._mic.stop():await this._mic.start(),this._micPerm=await this._mic.queryPermission()};this._open=async()=>{let t=this._active?.lock;if(!(!t||!this.hass)){this._openStatus="opening";try{await this.hass.callService("lock","unlock",{entity_id:t}),this._openStatus="opened"}catch{this._openStatus="error"}this._openReset&&clearTimeout(this._openReset),this._openReset=window.setTimeout(()=>{this._openStatus="idle",this.requestUpdate()},bt)}};this._dismiss=()=>{this.dispatchEvent(new CustomEvent("eg-dismiss",{bubbles:!0,composed:!0}))};this._retry=()=>{this.hass?.callService("elektronny_gorod","answer")}}setConfig(t){let i=t?.doorbells??(t?.call_state?[{call_state:t.call_state,doorbell_camera:t.doorbell_camera,lock:t.lock,name:t.name,address:t.address}]:[]);if(!i.length||i.some(s=>!s.call_state))throw new Error("eg-intercom-call-card: \u0443\u043A\u0430\u0436\u0438\u0442\u0435 'doorbells' (\u0441 call_state) \u0438\u043B\u0438 'call_state'");this._config=t,this._doorbells=i,this._openAction=Be(t.open_action,qe())}getCardSize(){return 8}static getStubConfig(){return{camera:"",doorbells:[{call_state:"",doorbell_camera:"",lock:""}]}}disconnectedCallback(){super.disconnectedCallback(),this._mic.stop(),this._stopTick(),this._errHide&&clearTimeout(this._errHide),this._openReset&&clearTimeout(this._openReset),this._endedHide&&clearTimeout(this._endedHide)}_phaseOf(t){let i=this.hass?.states[t.call_state]?.state;return He(i)}get _active(){let t=this._doorbells.find(i=>se.has(this._phaseOf(i))&&!this._errDismissed.has(i.call_state));if(t)return t;if(this._endedEntity)return this._doorbells.find(i=>i.call_state===this._endedEntity)}get _phase(){let t=this._active;if(!t)return"idle";let i=this._phaseOf(t);return se.has(i)?i:t.call_state===this._endedEntity?"ended":"idle"}get _intercomName(){let t=this._active;if(t?.name)return t.name;let s=(t?this.hass?.states[t.call_state]?.attributes:void 0)?.intercom_name;return(typeof s=="string"?s.replace(/\s+/g," ").trim():"")||this._config.name||"\u0414\u043E\u043C\u043E\u0444\u043E\u043D"}get _address(){return this._active?.address??this._config.address??""}get _startedAtMs(){let t=this._active,i=t?this.hass?.states[t.call_state]?.attributes?.started_at:void 0;if(typeof i!="string")return;let s=Date.parse(i);return Number.isNaN(s)?void 0:s}willUpdate(t){if(!t.has("hass"))return;for(let n of this._doorbells){let o=this._phaseOf(n),p=this._prevPhases.get(n.call_state);this._prevPhases.set(n.call_state,o),this._errDismissed.has(n.call_state)&&o!=="error"&&this._errDismissed.delete(n.call_state),o==="ended"&&p!==void 0&&se.has(p)&&p!=="error"&&this._enterEnded(n),this._endedEntity===n.call_state&&se.has(o)&&this._clearEnded()}let i=this._active,s=i?`${i.call_state}|${this._phase}`:"idle";s!==this._prevKey&&(this._onPhase(this._phase,i),this._prevKey=s)}_enterEnded(t){this._endedDuration=this._durationOf(t),this._endedEntity=t.call_state,this._endedHide&&clearTimeout(this._endedHide),this._endedHide=window.setTimeout(()=>this._clearEnded(),xt)}_durationOf(t){let i=this.hass?.states[t.call_state]?.attributes?.started_at;if(typeof i!="string")return"";let s=Date.parse(i);return Number.isNaN(s)?"":this._mmss(Math.max(0,Math.floor((Date.now()-s)/1e3)))}_onPhase(t,i){t==="active"?this._enterActive():t==="ringing"?(this._ringingSince=Date.now(),this._startTick()):this._exitActive(),t==="error"&&i&&this._scheduleErrDismiss(i.call_state),(t==="idle"||t==="ringing")&&(this._openStatus="idle")}async _enterActive(){this._muted=!1,this._audioBlocked=this._detectAudioBlocked(),this._startTick(),this._micPerm=await this._mic.queryPermission(),this._config.mic_autostart!==!1&&je(this._micPerm,this._mic.secure)&&await this._mic.start()}_detectAudioBlocked(){let t=navigator.userActivation;return t?!t.hasBeenActive:!1}_exitActive(){this._mic.stop(),this._stopTick(),this._audioBlocked=!1}_startTick(){this._stopTick(),this._now=Date.now(),this._tick=window.setInterval(()=>{this._now=Date.now()},1e3)}_stopTick(){this._tick&&(clearInterval(this._tick),this._tick=void 0)}_scheduleErrDismiss(t){this._errHide&&clearTimeout(this._errHide),this._errHide=window.setTimeout(()=>{this._errDismissed=new Set(this._errDismissed).add(t),this.requestUpdate()},_t)}_timerText(){let t=this._startedAtMs;if(t===void 0)return"";let i=Math.max(0,Math.floor((this._now-t)/1e3));return this._mmss(i)}_mmss(t){let i=String(Math.floor(t/60)).padStart(2,"0"),s=String(t%60).padStart(2,"0");return`${i}:${s}`}_answerWindow(){if(!this._ringingSince)return{text:"",fraction:0};let t=Math.max(0,Ve-(this._now-this._ringingSince)),i=Math.ceil(t/1e3);return{text:`${Math.floor(i/60)}:${String(i%60).padStart(2,"0")}`,fraction:t/Ve}}_stageState(t,i,s){if(s==="ended")return"ended";if(t.isError)return"connection_lost";let n=i?this.hass?.states[i]:void 0;return!n||n.state==="unavailable"?"camera_off":"live"}get _micNeedsPermission(){return this._config.mic===!1||this._phase!=="active"||this._micActive?!1:!this._mic.secure||this._micPerm==="denied"||this._micPerm==="prompt"}get _micBlocked(){return!this._mic.secure||this._micPerm==="denied"}_timestamp(t){if(t!=="live")return"";let i=new Date(this._now),s=n=>String(n).padStart(2,"0");return`${s(i.getDate())}-${s(i.getMonth()+1)}-${i.getFullYear()} ${s(i.getHours())}:${s(i.getMinutes())}:${s(i.getSeconds())}`}render(){let t=this._active;if(!t)return this._renderIdle();let i=this._phase,s=Oe(i),n=ze(s.video,{camera:this._config.camera,doorbell_camera:t.doorbell_camera}),o=this._stageState(s,n,i);return l`
      <ha-card class="phase-${i}">
        <div class="content">
          ${this._renderHeader()}
          ${this._renderStatus(s,i)}
          <div class="stage">
            <eg-call-stage
              .hass=${this.hass}
              .entity=${n}
              .muted=${this._muted}
              .live=${o==="live"}
              .soundOff=${i==="active"&&this._muted&&!this._audioBlocked}
              .timestamp=${this._timestamp(o)}
              .stageState=${o}
              .audioBlocked=${this._audioBlocked}
              @unmute=${this._unmute}
            ></eg-call-stage>
          </div>
          ${this._micNeedsPermission?this._renderMicBanner():d}
          <div class="open-area">
            ${s.showOpen?this._renderOpen():d}
          </div>
          ${this._renderActions(s)}
        </div>
      </ha-card>
    `}_renderHeader(){let t=this._address;return l`
      <header>
        <div class="hgroup">
          <span class="name" title=${this._intercomName}>${this._intercomName}</span>
          ${t?l`<span class="addr">${t}</span>`:d}
        </div>
        <button class="close" @click=${this._dismiss} aria-label="Свернуть">
          <eg-icon name="x"></eg-icon>
        </button>
      </header>
    `}_renderStatus(t,i){let s=t.showTimer&&this._config.timer!=="off",n=t.showAnswerWindow?this._answerWindow():null;return l`
      <div class="statusrow">
        <div class="strow">
          <span class="badge" style="--badge:${De(i)}">
            <span class="dot" aria-hidden="true"></span>
            <span>${vt[i]??""}</span>
          </span>
          ${n?l`<span class="countdown"><eg-icon name="timer"></eg-icon>${n.text}</span>`:s?l`<span class="timer">${this._timerText()}</span>`:i==="ended"&&this._endedDuration?l`<span class="timer ended-dur">${this._endedDuration}</span>`:d}
        </div>
        ${n?l`<div class="window"><div class="fill" style="width:${n.fraction*100}%"></div></div>`:d}
      </div>
    `}_doorbellNames(){return this._doorbells.map(t=>{let i=this.hass?.states[t.call_state]?.attributes?.intercom_name;return t.name??(typeof i=="string"?i:"")}).filter(Boolean)}_renderIdle(){let t=this._doorbellNames();return l`
      <ha-card class="idle">
        <div class="idle-stage" role="status">
          <eg-icon name="door-open" class="idle-ic"></eg-icon>
          <div class="idle-title">${this._config.idle_text??"\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u044B\u0437\u043E\u0432\u0430"}</div>
          <div class="idle-sub">Экран покажет видео, звук и кнопки при звонке домофона</div>
          ${t.length?l`<div class="idle-chips">
                ${t.map(i=>l`<span class="chip"><eg-icon name="circle-check"></eg-icon>${i}</span>`)}
              </div>`:d}
        </div>
      </ha-card>
    `}_renderMicBanner(){return l`
      <div class="mic-banner" role="alert">
        <eg-icon name="mic-off"></eg-icon>
        <div class="mb-text">
          <span class="mb-title">Нет доступа к микрофону</span>
          <span class="mb-sub">Вас не слышно. Разрешите доступ в браузере.</span>
        </div>
        <button class="mb-btn" @click=${this._toggleMic}>Разрешить</button>
      </div>
    `}_renderOpen(){return l`
      <eg-open-control
        .mode=${this._openAction}
        .status=${this._openStatus}
        ?disabled=${!this._active?.lock}
        @open=${this._open}
      ></eg-open-control>
    `}_circle(t,i,s,n=""){return l`
      <button class="circle ${n}" @click=${s} aria-label=${i}>
        <span class="ic"><eg-icon name=${t}></eg-icon></span>
        <small>${i}</small>
      </button>
    `}_renderActions(t){return l`<div class="actions">${t.actions.map(i=>this._renderAction(i))}</div>`}_renderAction(t){switch(t){case"accept":return this._circle("phone","\u041F\u0440\u0438\u043D\u044F\u0442\u044C",this._answer,"accept");case"reject":return this._circle("phone-off","\u041E\u0442\u043A\u043B\u043E\u043D\u0438\u0442\u044C",this._hangup,"reject");case"cancel":return this._circle("phone-off","\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C",this._hangup,"reject");case"connecting":return this._spinnerBtn("\u0421\u043E\u0435\u0434\u0438\u043D\u044F\u0435\u043C\u2026");case"mic":return this._config.mic===!1?d:this._renderMic();case"sound":return this._audioBlocked?this._circle("volume-x","\u0417\u0432\u0443\u043A \u0432\u044B\u043A\u043B.",this._unmute,"warn"):this._circle(this._muted?"volume-x":"volume-2","\u0417\u0432\u0443\u043A",this._toggleMute);case"hangup":return this._circle("phone-off","\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C",this._hangup,"reject");case"retry":return this._circle("refresh-cw","\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",this._retry,"retry");case"close":return this._circle("x","\u0417\u0430\u043A\u0440\u044B\u0442\u044C",this._clearEnded);default:return d}}_spinnerBtn(t){return l`
      <div class="circle spinner-btn" role="status" aria-label=${t} aria-busy="true">
        <span class="ic"><eg-icon class="spin" name="loader-circle"></eg-icon></span>
        <small>${t}</small>
      </div>
    `}_renderMic(){if(this._micBlocked)return this._circle("mic-off","\u041D\u0435\u0442 \u0434\u043E\u0441\u0442\u0443\u043F\u0430",this._toggleMic,"mic-blocked");let t=this._micActive?"mic":"mic-off",i=this._micActive?"\u0412\u044B\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D":"\u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D";return l`<button class="circle" @click=${this._toggleMic} aria-label=${i}>
      <span class="ic"><eg-icon name=${t}></eg-icon></span><small>Микрофон</small>
    </button>`}};v.styles=[z,b`
      :host {
        display: block;
        height: 100%;
        /* адаптив по собственной ширине карточки (телефон / планшет / десктоп / панель) */
        container-type: inline-size;
      }
      ha-card {
        height: 100%;
        box-sizing: border-box;
        background: var(--eg-card);
        border-radius: var(--eg-r-card);
      }
      .content {
        display: flex;
        flex-direction: column;
        gap: 20px;
        padding: 6px 16px 28px;
        box-sizing: border-box;
      }
      /* ---- шапка: имя + адрес + свернуть ---- */
      header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }
      .hgroup {
        display: flex;
        flex-direction: column;
        gap: 3px;
        min-width: 0;
      }
      .name {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.15;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .addr {
        font-size: 13px;
        color: var(--eg-text-2);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .close {
        flex: none;
        width: 44px;
        height: 44px;
        border: none;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        color: var(--eg-text-2);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
      }
      .close eg-icon {
        --eg-icon-size: 20px;
      }
      /* ---- статус-строка: бейдж + таймер/countdown + окно ответа ---- */
      .statusrow {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .strow {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 5px 12px;
        border-radius: var(--eg-r-full);
        font-size: 13px;
        font-weight: 600;
        color: var(--badge, var(--eg-text-2));
        background: color-mix(in srgb, var(--badge, var(--eg-text-2)) 18%, transparent);
      }
      .badge .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
      }
      .countdown {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 15px;
        color: var(--eg-text-2);
      }
      .countdown eg-icon {
        --eg-icon-size: 15px;
      }
      .timer {
        font-family: var(--eg-mono);
        font-size: 17px;
        font-weight: 600;
        color: var(--eg-text);
        font-variant-numeric: tabular-nums;
      }
      .timer.ended-dur {
        color: var(--eg-text-3);
        font-weight: 500;
      }
      .window {
        width: 100%;
        height: 4px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
      }
      .window .fill {
        height: 100%;
        border-radius: var(--eg-r-full);
        background: var(--eg-warning);
        transition: width 1s linear;
      }
      /* ---- баннер «нет доступа к микрофону» ---- */
      .mic-banner {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        border-radius: var(--eg-r-md);
        background: var(--eg-warning-bg);
      }
      .mic-banner > eg-icon {
        --eg-icon-size: 20px;
        color: var(--eg-warning);
      }
      .mb-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        flex: 1;
        min-width: 0;
      }
      .mb-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--eg-warning);
      }
      .mb-sub {
        font-size: 12px;
        color: var(--eg-text-2);
      }
      .mb-btn {
        flex: none;
        border: 1px solid var(--eg-warning);
        background: transparent;
        color: var(--eg-warning);
        font: inherit;
        font-size: 13px;
        font-weight: 600;
        border-radius: var(--eg-r-full);
        padding: 6px 14px;
        cursor: pointer;
      }
      /* ---- видео-стейдж ---- */
      .stage {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        border-radius: var(--eg-r-md);
        overflow: hidden;
        background: var(--eg-elevated);
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .spin {
          animation: none;
        }
      }
      /* ---- зона «Открыть» ---- */
      .open-area {
        display: flex;
        justify-content: center;
      }
      .open-area eg-open-control {
        width: 100%;
      }
      /* ---- ряд действий: круги top-align (как в макете), gap 28 ---- */
      .actions {
        display: flex;
        gap: 28px;
        justify-content: center;
        align-items: flex-start;
        flex-wrap: wrap;
      }
      .circle {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        border: none;
        background: none;
        cursor: pointer;
        color: var(--eg-text);
        font: inherit;
        padding: 0;
      }
      .circle .ic {
        width: 68px;
        height: 68px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .circle .ic eg-icon {
        --eg-icon-size: 28px;
      }
      .circle small {
        font-size: 12px;
        font-weight: 500;
        color: var(--eg-text-2);
      }
      .circle[disabled] {
        cursor: not-allowed;
        opacity: 0.5;
      }
      /* Все кнопки ряда — единый стиль: круг 68, иконка 28, подпись fs12/fw500/text-2.
         Акцент действия — только ЦВЕТОМ круга (см. call-card-ux-production.md §6/§9). */
      .circle.accept .ic {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .circle.reject .ic {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
      .circle.retry .ic {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      /* audio_blocked: «Звук выкл.» — warning-иконка на elevated */
      .circle.warn .ic {
        color: var(--eg-warning);
      }
      .circle.warn small {
        color: var(--eg-warning);
      }
      /* микрофон недоступен: красный индикатор «Нет доступа» (iUNo1) */
      .circle.mic-blocked .ic {
        background: var(--eg-error-bg);
        color: var(--eg-error);
      }
      .circle.mic-blocked small {
        color: var(--eg-error);
      }
      /* «Соединяем…» — неинтерактивно, приглушённый крутящийся loader */
      .spinner-btn {
        cursor: default;
      }
      .spinner-btn small {
        color: var(--eg-text-3);
      }
      .spinner-btn .ic eg-icon.spin {
        color: var(--eg-text-2);
        animation: spin 0.9s linear infinite;
      }
      /* ---- idle-заглушка (детально — в Slice 5) ---- */
      ha-card.idle {
        height: 100%;
        box-sizing: border-box;
        display: flex;
        align-items: stretch;
        justify-content: center;
        padding: 20px 16px;
      }
      .idle-stage {
        width: 100%;
        aspect-ratio: 16 / 9;
        border-radius: var(--eg-r-md);
        background: var(--eg-elevated);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-align: center;
        padding: 14px;
        box-sizing: border-box;
        color: var(--eg-text-2);
      }
      .idle-stage .idle-ic {
        --eg-icon-size: 52px;
        color: var(--eg-primary);
        opacity: 0.75;
      }
      .idle-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--eg-text);
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
        border-radius: var(--eg-r-full);
        background: var(--eg-card);
        color: var(--eg-text);
        font-size: 0.8rem;
        font-weight: 600;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
      }
      .chip eg-icon {
        --eg-icon-size: 16px;
        color: var(--eg-success);
      }
    `],c([u({attribute:!1})],v.prototype,"hass",2),c([f()],v.prototype,"_config",2),c([f()],v.prototype,"_muted",2),c([f()],v.prototype,"_audioBlocked",2),c([f()],v.prototype,"_micActive",2),c([f()],v.prototype,"_micPerm",2),c([f()],v.prototype,"_openStatus",2),c([f()],v.prototype,"_now",2),c([f()],v.prototype,"_ringingSince",2),c([f()],v.prototype,"_errDismissed",2),c([f()],v.prototype,"_endedEntity",2),c([f()],v.prototype,"_endedDuration",2),v=c([A("eg-intercom-call-card")],v);window.customCards=window.customCards||[];window.customCards.push({type:"eg-intercom-call-card",name:"\u042D\u0413 \u0414\u043E\u043C\u043E\u0444\u043E\u043D \u2014 \u042D\u043A\u0440\u0430\u043D \u0432\u044B\u0437\u043E\u0432\u0430",description:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432 \u0438 \u0440\u0430\u0437\u0433\u043E\u0432\u043E\u0440 \u0441 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u043E\u043C: \u0432\u0438\u0434\u0435\u043E+\u0437\u0432\u0443\u043A, \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C, \u043F\u0440\u0438\u043D\u044F\u0442\u044C/\u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C, \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D. \u041E\u0434\u043D\u0430 \u043A\u0430\u0440\u0442\u0430 \u043D\u0430 \u0432\u0441\u0435 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u044B.",preview:!1});export{v as EgIntercomCallCard};
