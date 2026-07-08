/* eg-intercom-call-card — собранный бандл. Источник: frontend/src/. Не редактировать вручную. */
var Ge=Object.defineProperty;var Fe=Object.getOwnPropertyDescriptor;var p=(s,t,e,i)=>{for(var r=i>1?void 0:i?Fe(t,e):t,a=s.length-1,n;a>=0;a--)(n=s[a])&&(r=(i?n(t,e,r):n(r))||r);return i&&r&&Ge(t,e,r),r};var Y=globalThis,X=Y.ShadowRoot&&(Y.ShadyCSS===void 0||Y.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ae=Symbol(),_e=new WeakMap,D=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==ae)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(X&&t===void 0){let i=e!==void 0&&e.length===1;i&&(t=_e.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&_e.set(e,t))}return t}toString(){return this.cssText}},be=s=>new D(typeof s=="string"?s:s+"",void 0,ae),b=(s,...t)=>{let e=s.length===1?s[0]:t.reduce((i,r,a)=>i+(n=>{if(n._$cssResult$===!0)return n.cssText;if(typeof n=="number")return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+s[a+1],s[0]);return new D(e,s,ae)},xe=(s,t)=>{if(X)s.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let i=document.createElement("style"),r=Y.litNonce;r!==void 0&&i.setAttribute("nonce",r),i.textContent=e.cssText,s.appendChild(i)}},ne=X?s=>s:s=>s instanceof CSSStyleSheet?(t=>{let e="";for(let i of t.cssRules)e+=i.cssText;return be(e)})(s):s;var{is:Ye,defineProperty:Xe,getOwnPropertyDescriptor:Ze,getOwnPropertyNames:Je,getOwnPropertySymbols:Qe,getPrototypeOf:et}=Object,Z=globalThis,ye=Z.trustedTypes,tt=ye?ye.emptyScript:"",it=Z.reactiveElementPolyfillSupport,B=(s,t)=>s,L={toAttribute(s,t){switch(t){case Boolean:s=s?tt:null;break;case Object:case Array:s=s==null?s:JSON.stringify(s)}return s},fromAttribute(s,t){let e=s;switch(t){case Boolean:e=s!==null;break;case Number:e=s===null?null:Number(s);break;case Object:case Array:try{e=JSON.parse(s)}catch{e=null}}return e}},J=(s,t)=>!Ye(s,t),we={attribute:!0,type:String,converter:L,reflect:!1,useDefault:!1,hasChanged:J};Symbol.metadata??=Symbol("metadata"),Z.litPropertyMetadata??=new WeakMap;var k=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=we){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let i=Symbol(),r=this.getPropertyDescriptor(t,i,e);r!==void 0&&Xe(this.prototype,t,r)}}static getPropertyDescriptor(t,e,i){let{get:r,set:a}=Ze(this.prototype,t)??{get(){return this[e]},set(n){this[e]=n}};return{get:r,set(n){let d=r?.call(this);a?.call(this,n),this.requestUpdate(t,d,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??we}static _$Ei(){if(this.hasOwnProperty(B("elementProperties")))return;let t=et(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(B("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(B("properties"))){let e=this.properties,i=[...Je(e),...Qe(e)];for(let r of i)this.createProperty(r,e[r])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[i,r]of e)this.elementProperties.set(i,r)}this._$Eh=new Map;for(let[e,i]of this.elementProperties){let r=this._$Eu(e,i);r!==void 0&&this._$Eh.set(r,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let i=new Set(t.flat(1/0).reverse());for(let r of i)e.unshift(ne(r))}else t!==void 0&&e.push(ne(t));return e}static _$Eu(t,e){let i=e.attribute;return i===!1?void 0:typeof i=="string"?i:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return xe(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){let i=this.constructor.elementProperties.get(t),r=this.constructor._$Eu(t,i);if(r!==void 0&&i.reflect===!0){let a=(i.converter?.toAttribute!==void 0?i.converter:L).toAttribute(e,i.type);this._$Em=t,a==null?this.removeAttribute(r):this.setAttribute(r,a),this._$Em=null}}_$AK(t,e){let i=this.constructor,r=i._$Eh.get(t);if(r!==void 0&&this._$Em!==r){let a=i.getPropertyOptions(r),n=typeof a.converter=="function"?{fromAttribute:a.converter}:a.converter?.fromAttribute!==void 0?a.converter:L;this._$Em=r;let d=n.fromAttribute(e,a.type);this[r]=d??this._$Ej?.get(r)??d,this._$Em=null}}requestUpdate(t,e,i,r=!1,a){if(t!==void 0){let n=this.constructor;if(r===!1&&(a=this[t]),i??=n.getPropertyOptions(t),!((i.hasChanged??J)(a,e)||i.useDefault&&i.reflect&&a===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,i))))return;this.C(t,e,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:r,wrapped:a},n){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??e??this[t]),a!==!0||n!==void 0)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),r===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[r,a]of this._$Ep)this[r]=a;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[r,a]of i){let{wrapped:n}=a,d=this[r];n!==!0||this._$AL.has(r)||d===void 0||this.C(r,void 0,a,d)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(e)):this._$EM()}catch(i){throw t=!1,this._$EM(),i}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};k.elementStyles=[],k.shadowRootOptions={mode:"open"},k[B("elementProperties")]=new Map,k[B("finalized")]=new Map,it?.({ReactiveElement:k}),(Z.reactiveElementVersions??=[]).push("2.1.2");var ue=globalThis,$e=s=>s,Q=ue.trustedTypes,Ae=Q?Q.createPolicy("lit-html",{createHTML:s=>s}):void 0,Ee="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,Ce="?"+P,rt=`<${Ce}>`,C=document,q=()=>C.createComment(""),V=s=>s===null||typeof s!="object"&&typeof s!="function",ge=Array.isArray,st=s=>ge(s)||typeof s?.[Symbol.iterator]=="function",oe=`[ 	
\f\r]`,j=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ke=/-->/g,Se=/>/g,T=RegExp(`>|${oe}(?:([^\\s"'>=/]+)(${oe}*=${oe}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Me=/'/g,Pe=/"/g,Re=/^(?:script|style|textarea|title)$/i,me=s=>(t,...e)=>({_$litType$:s,strings:t,values:e}),o=me(1),Pt=me(2),Tt=me(3),S=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),Te=new WeakMap,E=C.createTreeWalker(C,129);function He(s,t){if(!ge(s)||!s.hasOwnProperty("raw"))throw Error("invalid template strings array");return Ae!==void 0?Ae.createHTML(t):t}var at=(s,t)=>{let e=s.length-1,i=[],r,a=t===2?"<svg>":t===3?"<math>":"",n=j;for(let d=0;d<e;d++){let l=s[d],g,m,h=-1,x=0;for(;x<l.length&&(n.lastIndex=x,m=n.exec(l),m!==null);)x=n.lastIndex,n===j?m[1]==="!--"?n=ke:m[1]!==void 0?n=Se:m[2]!==void 0?(Re.test(m[2])&&(r=RegExp("</"+m[2],"g")),n=T):m[3]!==void 0&&(n=T):n===T?m[0]===">"?(n=r??j,h=-1):m[1]===void 0?h=-2:(h=n.lastIndex-m[2].length,g=m[1],n=m[3]===void 0?T:m[3]==='"'?Pe:Me):n===Pe||n===Me?n=T:n===ke||n===Se?n=j:(n=T,r=void 0);let y=n===T&&s[d+1].startsWith("/>")?" ":"";a+=n===j?l+rt:h>=0?(i.push(g),l.slice(0,h)+Ee+l.slice(h)+P+y):l+P+(h===-2?d:y)}return[He(s,a+(s[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),i]},I=class s{constructor({strings:t,_$litType$:e},i){let r;this.parts=[];let a=0,n=0,d=t.length-1,l=this.parts,[g,m]=at(t,e);if(this.el=s.createElement(g,i),E.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(r=E.nextNode())!==null&&l.length<d;){if(r.nodeType===1){if(r.hasAttributes())for(let h of r.getAttributeNames())if(h.endsWith(Ee)){let x=m[n++],y=r.getAttribute(h).split(P),F=/([.?@])?(.*)/.exec(x);l.push({type:1,index:a,name:F[2],strings:y,ctor:F[1]==="."?le:F[1]==="?"?de:F[1]==="@"?pe:U}),r.removeAttribute(h)}else h.startsWith(P)&&(l.push({type:6,index:a}),r.removeAttribute(h));if(Re.test(r.tagName)){let h=r.textContent.split(P),x=h.length-1;if(x>0){r.textContent=Q?Q.emptyScript:"";for(let y=0;y<x;y++)r.append(h[y],q()),E.nextNode(),l.push({type:2,index:++a});r.append(h[x],q())}}}else if(r.nodeType===8)if(r.data===Ce)l.push({type:2,index:a});else{let h=-1;for(;(h=r.data.indexOf(P,h+1))!==-1;)l.push({type:7,index:a}),h+=P.length-1}a++}}static createElement(t,e){let i=C.createElement("template");return i.innerHTML=t,i}};function H(s,t,e=s,i){if(t===S)return t;let r=i!==void 0?e._$Co?.[i]:e._$Cl,a=V(t)?void 0:t._$litDirective$;return r?.constructor!==a&&(r?._$AO?.(!1),a===void 0?r=void 0:(r=new a(s),r._$AT(s,e,i)),i!==void 0?(e._$Co??=[])[i]=r:e._$Cl=r),r!==void 0&&(t=H(s,r._$AS(s,t.values),r,i)),t}var ce=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:i}=this._$AD,r=(t?.creationScope??C).importNode(e,!0);E.currentNode=r;let a=E.nextNode(),n=0,d=0,l=i[0];for(;l!==void 0;){if(n===l.index){let g;l.type===2?g=new W(a,a.nextSibling,this,t):l.type===1?g=new l.ctor(a,l.name,l.strings,this,t):l.type===6&&(g=new he(a,this,t)),this._$AV.push(g),l=i[++d]}n!==l?.index&&(a=E.nextNode(),n++)}return E.currentNode=C,r}p(t){let e=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}},W=class s{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,r){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=H(this,t,e),V(t)?t===c||t==null||t===""?(this._$AH!==c&&this._$AR(),this._$AH=c):t!==this._$AH&&t!==S&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):st(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==c&&V(this._$AH)?this._$AA.nextSibling.data=t:this.T(C.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:i}=t,r=typeof i=="number"?this._$AC(t):(i.el===void 0&&(i.el=I.createElement(He(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(e);else{let a=new ce(r,this),n=a.u(this.options);a.p(e),this.T(n),this._$AH=a}}_$AC(t){let e=Te.get(t.strings);return e===void 0&&Te.set(t.strings,e=new I(t)),e}k(t){ge(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,i,r=0;for(let a of t)r===e.length?e.push(i=new s(this.O(q()),this.O(q()),this,this.options)):i=e[r],i._$AI(a),r++;r<e.length&&(this._$AR(i&&i._$AB.nextSibling,r),e.length=r)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let i=$e(t).nextSibling;$e(t).remove(),t=i}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},U=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,r,a){this.type=1,this._$AH=c,this._$AN=void 0,this.element=t,this.name=e,this._$AM=r,this.options=a,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=c}_$AI(t,e=this,i,r){let a=this.strings,n=!1;if(a===void 0)t=H(this,t,e,0),n=!V(t)||t!==this._$AH&&t!==S,n&&(this._$AH=t);else{let d=t,l,g;for(t=a[0],l=0;l<a.length-1;l++)g=H(this,d[i+l],e,l),g===S&&(g=this._$AH[l]),n||=!V(g)||g!==this._$AH[l],g===c?t=c:t!==c&&(t+=(g??"")+a[l+1]),this._$AH[l]=g}n&&!r&&this.j(t)}j(t){t===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},le=class extends U{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===c?void 0:t}},de=class extends U{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==c)}},pe=class extends U{constructor(t,e,i,r,a){super(t,e,i,r,a),this.type=5}_$AI(t,e=this){if((t=H(this,t,e,0)??c)===S)return;let i=this._$AH,r=t===c&&i!==c||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,a=t!==c&&(i===c||r);r&&this.element.removeEventListener(this.name,this,i),a&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},he=class{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){H(this,t)}};var nt=ue.litHtmlPolyfillSupport;nt?.(I,W),(ue.litHtmlVersions??=[]).push("3.3.3");var Ue=(s,t,e)=>{let i=e?.renderBefore??t,r=i._$litPart$;if(r===void 0){let a=e?.renderBefore??null;i._$litPart$=r=new W(t.insertBefore(q(),a),a,void 0,e??{})}return r._$AI(s),r};var fe=globalThis,_=class extends k{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Ue(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};_._$litElement$=!0,_.finalized=!0,fe.litElementHydrateSupport?.({LitElement:_});var ot=fe.litElementPolyfillSupport;ot?.({LitElement:_});(fe.litElementVersions??=[]).push("4.2.2");var A=s=>(t,e)=>{e!==void 0?e.addInitializer(()=>{customElements.define(s,t)}):customElements.define(s,t)};var ct={attribute:!0,type:String,converter:L,reflect:!1,hasChanged:J},lt=(s=ct,t,e)=>{let{kind:i,metadata:r}=e,a=globalThis.litPropertyMetadata.get(r);if(a===void 0&&globalThis.litPropertyMetadata.set(r,a=new Map),i==="setter"&&((s=Object.create(s)).wrapped=!0),a.set(e.name,s),i==="accessor"){let{name:n}=e;return{set(d){let l=t.get.call(this);t.set.call(this,d),this.requestUpdate(n,l,s,!0,d)},init(d){return d!==void 0&&this.C(n,void 0,s,d),d}}}if(i==="setter"){let{name:n}=e;return function(d){let l=this[n];t.call(this,d),this.requestUpdate(n,l,s,!0,d)}}throw Error("Unsupported decorator location: "+i)};function u(s){return(t,e)=>typeof e=="object"?lt(s,t,e):((i,r,a)=>{let n=r.hasOwnProperty(a);return r.constructor.createProperty(a,i),n?Object.getOwnPropertyDescriptor(r,a):void 0})(s,t,e)}function f(s){return u({...s,state:!0,attribute:!1})}var dt=new Set(["idle","ringing","connecting","active","ended","error"]);function Oe(s){return s&&dt.has(s)?s:"idle"}var O={visible:!1,video:"none",actions:[],showOpen:!1,showTimer:!1,showAnswerWindow:!1,busy:!1,isError:!1};function Ne(s){switch(s){case"ringing":return{...O,visible:!0,video:"doorbell",actions:["reject","accept"],showOpen:!0,showAnswerWindow:!0};case"connecting":return{...O,visible:!0,video:"doorbell",actions:["cancel","connecting"],showOpen:!0,busy:!0};case"active":return{...O,visible:!0,video:"call",actions:["mic","sound","hangup"],showOpen:!0,showTimer:!0};case"error":return{...O,visible:!0,video:"none",actions:["retry","hangup"],showOpen:!0,isError:!0};case"ended":return{...O,visible:!0,video:"call",actions:["close"],showOpen:!0};case"idle":default:return{...O}}}var ze={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},ie=s=>(...t)=>({_$litDirective$:s,values:t}),te=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,i){this._$Ct=t,this._$AM=e,this._$Ci=i}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var R=class extends te{constructor(t){if(super(t),this.it=c,t.type!==ze.CHILD)throw Error(this.constructor.directiveName+"() can only be used in child bindings")}render(t){if(t===c||t==null)return this._t=void 0,this.it=t;if(t===S)return t;if(typeof t!="string")throw Error(this.constructor.directiveName+"() called with a non-string value");if(t===this.it)return this._t;this.it=t;let e=[t];return e.raw=e,this._t={_$litType$:this.constructor.resultType,strings:e,values:[]}}};R.directiveName="unsafeHTML",R.resultType=1;var bi=ie(R);var K=class extends R{};K.directiveName="unsafeSVG",K.resultType=2;var De=ie(K);var pt={"key-round":'<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',lock:'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',"lock-open":'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',phone:'<path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"/>',"phone-off":'<path d="M10.1 13.9a14 14 0 0 0 3.732 2.668 1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2 18 18 0 0 1-12.728-5.272"/><path d="M22 2 2 22"/><path d="M4.76 13.582A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 .244.473"/>',mic:'<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',"mic-off":'<path d="M12 19v3"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M16.95 16.95A7 7 0 0 1 5 12v-2"/><path d="M18.89 13.23A7 7 0 0 0 19 12v-2"/><path d="m2 2 20 20"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/>',"volume-2":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',"volume-x":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/>',x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',timer:'<line x1="10" x2="14" y1="2" y2="2"/><line x1="12" x2="15" y1="14" y2="11"/><circle cx="12" cy="14" r="8"/>',"refresh-cw":'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',"door-open":'<path d="M11 20H2"/><path d="M11 4.562v16.157a1 1 0 0 0 1.242.97L19 20V5.562a2 2 0 0 0-1.515-1.94l-4-1A2 2 0 0 0 11 4.561z"/><path d="M11 4H8a2 2 0 0 0-2 2v14"/><path d="M14 12h.01"/><path d="M22 20h-3"/>',"video-off":'<path d="M10.66 6H14a2 2 0 0 1 2 2v2.5l5.248-3.062A.5.5 0 0 1 22 7.87v8.196"/><path d="M16 16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2"/><path d="m2 2 20 20"/>',"wifi-off":'<path d="M12 20h.01"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/><path d="M5 12.859a10 10 0 0 1 5.17-2.69"/><path d="M19 12.859a10 10 0 0 0-2.007-1.523"/><path d="M2 8.82a15 15 0 0 1 4.177-2.643"/><path d="M22 8.82a15 15 0 0 0-11.288-3.764"/><path d="m2 2 20 20"/>',"circle-check":'<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',"chevron-right":'<path d="m9 18 6-6-6-6"/>',"bell-ring":'<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M22 8c0-2.3-.8-4.3-2-6"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/>',"loader-circle":'<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',"door-closed":'<path d="M10 12h.01"/><path d="M18 20V6a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v14"/><path d="M2 20h20"/>'},N=class extends _{constructor(){super(...arguments);this.name=""}render(){let e=pt[this.name]??"";return o`<svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >${De(e)}</svg>`}};N.styles=b`
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
  `,p([u()],N.prototype,"name",2),N=p([A("eg-icon")],N);function Be(s,t){if(s==="call")return t.camera;if(s==="doorbell")return t.doorbell_camera??t.camera}var M=class extends _{constructor(){super(...arguments);this.muted=!1;this._provider="pending"}connectedCallback(){super.connectedCallback(),this._resolveProvider()}async _resolveProvider(){if(customElements.get("ha-camera-stream")){this._provider="ha";return}try{await window.loadCardHelpers?.()}catch{}customElements.get("ha-camera-stream")?this._provider="ha":customElements.get("webrtc-camera")?this._provider="webrtc":this._provider="none"}updated(e){this._provider==="webrtc"&&this._syncWebrtc(e)}_syncWebrtc(e){let i=this.renderRoot.querySelector("#webrtc-host");if(!(!i||!this.entity||!this.hass))if(e.has("entity")||e.has("_provider")||e.has("muted")||!this._webrtcEl){i.replaceChildren();let r=document.createElement("webrtc-camera");r.setConfig({entity:this.entity,muted:this.muted}),r.hass=this.hass,i.appendChild(r),this._webrtcEl=r}else this._webrtcEl.hass=this.hass}render(){if(!this.entity||!this.hass)return this._frame("video-off","\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u0438\u0434\u0435\u043E");let e=this.hass.states[this.entity];if(!e)return this._frame("video-off","\u041A\u0430\u043C\u0435\u0440\u0430 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u0430");switch(this._provider){case"pending":return this._frame("video-off","\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0432\u0438\u0434\u0435\u043E\u2026");case"ha":return o`
          <ha-camera-stream
            .hass=${this.hass}
            .stateObj=${e}
            .muted=${this.muted}
          ></ha-camera-stream>
        `;case"webrtc":return o`<div id="webrtc-host"></div>`;default:return this._frame("video-off","\u0412\u0438\u0434\u0435\u043E\u043F\u043B\u0435\u0435\u0440 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D \u2014 \u043E\u0431\u043D\u043E\u0432\u0438\u0442\u0435 HA \u0438\u043B\u0438 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0435 advanced-camera-card")}}_frame(e,i){return o`
      <div class="frame" role="img" aria-label=${i}>
        <eg-icon name=${e}></eg-icon>
        <span>${i}</span>
      </div>
      ${c}
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
  `,p([u({attribute:!1})],M.prototype,"hass",2),p([u()],M.prototype,"entity",2),p([u({type:Boolean})],M.prototype,"muted",2),p([f()],M.prototype,"_provider",2),M=p([A("eg-call-video")],M);var z=b`
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
`,ht={idle:"var(--eg-text-2)",ringing:"var(--eg-warning)",connecting:"var(--eg-primary)",active:"var(--eg-success)",ended:"var(--eg-text-2)",error:"var(--eg-error)"};function ve(s){return ht[s]??"var(--eg-text-2)"}function ut(s){switch(s){case"camera_off":return"placeholder-camera";case"connection_lost":return"placeholder-connection";case"ended":return"video-dimmed";default:return"video"}}var w=class extends _{constructor(){super(...arguments);this.muted=!1;this.live=!1;this.soundOff=!1;this.stageState="live";this.audioBlocked=!1;this._unmute=()=>{this.dispatchEvent(new CustomEvent("unmute",{bubbles:!0,composed:!0}))}}render(){let e=ut(this.stageState);return e==="placeholder-camera"?this._placeholder("video-off","muted","\u0412\u0438\u0434\u0435\u043E \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u043E","\u0410\u0443\u0434\u0438\u043E\u0432\u044B\u0437\u043E\u0432 \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0430\u0435\u0442\u0441\u044F"):e==="placeholder-connection"?this._placeholder("wifi-off","err","\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435 \u043F\u0440\u0435\u0440\u0432\u0430\u043D\u043E","\u041F\u0440\u043E\u0431\u0443\u0435\u043C \u0432\u043E\u0441\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C\u2026"):o`
      <eg-call-video .hass=${this.hass} .entity=${this.entity} .muted=${this.muted}></eg-call-video>
      ${e==="video-dimmed"?o`<div class="dim" aria-hidden="true"></div>`:c}
      <div class="top">
        ${this.live?o`<span class="live"><span class="live-dot" aria-hidden="true"></span>LIVE</span>`:c}
        ${this.soundOff?o`<span class="chip"><eg-icon name="volume-x"></eg-icon>Звук выкл.</span>`:c}
      </div>
      ${this.audioBlocked?o`
            <button class="tap" @click=${this._unmute} aria-label="Включить звук"></button>
            <span class="cta" aria-hidden="true">
              <eg-icon name="volume-x"></eg-icon>Нажмите, чтобы включить звук
            </span>
          `:c}
    `}_placeholder(e,i,r,a){return o`
      <div class="fallback ${i}" role="img" aria-label=${r}>
        <eg-icon name=${e}></eg-icon>
        <span class="fb-title">${r}</span>
        <span class="fb-sub">${a}</span>
      </div>
    `}};w.styles=[z,b`
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
        top: calc(12px * var(--eg-scale, 1));
        left: calc(12px * var(--eg-scale, 1));
        right: calc(12px * var(--eg-scale, 1));
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        pointer-events: none;
      }
      .live {
        display: inline-flex;
        align-items: center;
        gap: calc(6px * var(--eg-scale, 1));
        padding: calc(3px * var(--eg-scale, 1)) calc(9px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: calc(10px * var(--eg-scale, 1));
        font-weight: 600;
        letter-spacing: 0.04em;
      }
      .live-dot {
        width: calc(6px * var(--eg-scale, 1));
        height: calc(6px * var(--eg-scale, 1));
        border-radius: 50%;
        background: #fff;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: calc(6px * var(--eg-scale, 1));
        padding: calc(5px * var(--eg-scale, 1)) calc(10px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: rgba(0, 0, 0, 0.63);
        color: #fff;
        font-size: calc(11px * var(--eg-scale, 1));
      }
      .chip eg-icon {
        --eg-icon-size: calc(14px * var(--eg-scale, 1));
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
        bottom: calc(16px * var(--eg-scale, 1));
        transform: translateX(-50%);
        display: inline-flex;
        align-items: center;
        gap: calc(8px * var(--eg-scale, 1));
        padding: calc(10px * var(--eg-scale, 1)) calc(18px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: var(--eg-scrim);
        color: #fff;
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 500;
        white-space: nowrap;
        z-index: 3;
        pointer-events: none;
      }
      .cta eg-icon {
        --eg-icon-size: calc(18px * var(--eg-scale, 1));
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
        gap: calc(6px * var(--eg-scale, 1));
        text-align: center;
        padding: calc(12px * var(--eg-scale, 1));
        box-sizing: border-box;
      }
      .fallback eg-icon {
        --eg-icon-size: calc(36px * var(--eg-scale, 1));
        color: var(--eg-text-3);
      }
      .fallback.err eg-icon {
        color: var(--eg-error);
      }
      .fb-title {
        font-size: calc(15px * var(--eg-scale, 1));
        color: var(--eg-text);
      }
      .fb-sub {
        font-size: calc(12px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
    `],p([u({attribute:!1})],w.prototype,"hass",2),p([u()],w.prototype,"entity",2),p([u({type:Boolean})],w.prototype,"muted",2),p([u({type:Boolean})],w.prototype,"live",2),p([u({type:Boolean})],w.prototype,"soundOff",2),p([u()],w.prototype,"stageState",2),p([u({type:Boolean})],w.prototype,"audioBlocked",2),w=p([A("eg-call-stage")],w);function je(s){return s<0?0:s>1?1:s}function gt(s,t,e,i){let r=Math.max(1,e-i);return je((s-t-i/2)/r)}function mt(s,t){return je(s/Math.max(1,t))}var ft=.92,vt=800,Le=68,$=class extends _{constructor(){super(...arguments);this.mode="hold";this.disabled=!1;this.label="\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C";this.status="idle";this._progress=0;this._arming=!1;this._raf=0;this._holdStart=0;this._trackRect=null;this._knobW=Le;this._holdTick=()=>{if(this._progress=mt(performance.now()-this._holdStart,vt),this._progress>=1){this._commit();return}this._raf=requestAnimationFrame(this._holdTick)};this._onHoldDown=e=>{this.disabled||(e.target.setPointerCapture?.(e.pointerId),this._arming=!0,this._holdStart=performance.now(),this._raf=requestAnimationFrame(this._holdTick))};this._onHoldUp=()=>{this._progress<1&&this._reset()};this._onSlideDown=e=>{if(this.disabled)return;let i=e.currentTarget.closest(".track");this._trackRect=i?.getBoundingClientRect()??null;let r=i?.querySelector(".knob");this._knobW=r?.getBoundingClientRect().width||Le,e.target.setPointerCapture?.(e.pointerId),this._arming=!0};this._onSlideMove=e=>{!this._arming||!this._trackRect||(this._progress=gt(e.clientX,this._trackRect.left,this._trackRect.width,this._knobW))};this._onSlideUp=()=>{this._progress>=ft?this._commit():this._reset()};this._onTap=()=>{this.disabled||this._fireOpen()}}disconnectedCallback(){super.disconnectedCallback(),this._reset()}updated(e){e.has("status")&&(this.status==="idle"||this.status==="error")&&(this._progress=0)}_fireOpen(){this.dispatchEvent(new CustomEvent("open",{bubbles:!0,composed:!0}))}_reset(){this._raf&&cancelAnimationFrame(this._raf),this._raf=0,this._arming=!1,this._progress=0,this._trackRect=null}_commit(){this._raf&&cancelAnimationFrame(this._raf),this._raf=0,this._arming=!1,this._progress=1,this._trackRect=null,this._fireOpen()}render(){let e=this.mode==="tap"?this._renderTap():this.mode==="slide"?this._renderSlide():this._renderHold();return o`
      <div class="wrap" style="--eg-prog:${this._vp()}">
        ${e}
        ${this._caption()}
      </div>
    `}_caption(){let e="",i="";return this.status==="opened"?(e="\u0414\u0432\u0435\u0440\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u0430",i="st-opened"):this.status==="error"?(e="\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u044C \xB7 \u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",i="st-error"):this.status==="opening"?e="":this.mode==="slide"&&(e="\u0421\u0434\u0432\u0438\u043D\u044C\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C"),o`<span class="caption ${i}">${e||o`&nbsp;`}</span>`}_labelText(){return this.status==="opened"?"\u041E\u0442\u043A\u0440\u044B\u0442\u043E":this.status==="opening"?"\u041E\u0442\u043A\u0440\u044B\u0432\u0430\u044E\u2026":this.mode==="slide"?"\u041E\u0442\u043A\u0440\u044B\u0442\u044C":"\u0423\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0439\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C"}_barIcon(){return this.status==="opening"?"loader-circle":this.status==="opened"?"lock-open":"key-round"}_knobIcon(){return this.status==="opening"?"loader-circle":"key-round"}_vp(){return this.status==="opening"||this.status==="opened"?1:this._progress}_statusClass(){return this.status==="opened"?"st-opened":this.status==="opening"?"st-opening":this.status==="error"?"st-error":""}_renderTap(){return o`
      <button class="pill tap ${this._statusClass()}" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this.label}>
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `}_renderHold(){return o`
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
    `}_renderSlide(){return o`
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
          class="knob ${this.disabled?"off":""} ${this.status==="opening"?"loading":""}"
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
        gap: calc(8px * var(--eg-scale, 1));
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
      /* ---- slide: трек 300×80 в масштабе 1 (макет: центрирован, не на всю
         ширину); при --eg-scale трек/ключ растут пропорционально, ширина не
         превышает контейнер (min(...,100%)) — на панели слайдер крупный ---- */
      .track {
        position: relative;
        width: min(calc(300px * var(--eg-scale, 1)), 100%);
        height: calc(80px * var(--eg-scale, 1));
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
        width: calc(
          40px * var(--eg-scale, 1) + var(--eg-prog, 0) * (100% - 80px * var(--eg-scale, 1))
        );
        transition: none;
      }
      /* открытие (loading): доведено до конца — заливка на всю ширину + пульс */
      .track.st-opening .fill {
        width: 100%;
        background: var(--eg-primary);
        opacity: 0.15;
        animation: eg-pulse 1.1s ease-in-out infinite;
      }
      /* закрытый замок под ключом (проявляется при отъезде): иконка 20, центр под ключом */
      .lock-under {
        position: absolute;
        left: calc(30px * var(--eg-scale, 1));
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
        color: var(--eg-text-3);
        z-index: 0;
      }
      /* торец: открытый замок (макет: иконка 20, центр 28px от правого края) */
      .end {
        position: absolute;
        right: calc(18px * var(--eg-scale, 1));
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
        color: var(--eg-text-3);
        z-index: 0;
      }
      .track .label {
        position: relative;
        z-index: 1;
        font-size: calc(17px * var(--eg-scale, 1));
        font-weight: 600;
        color: var(--eg-text);
      }
      .knob {
        position: absolute;
        top: calc(6px * var(--eg-scale, 1));
        left: calc(6px * var(--eg-scale, 1) + var(--eg-prog, 0) * (100% - 80px * var(--eg-scale, 1)));
        width: calc(68px * var(--eg-scale, 1));
        height: calc(68px * var(--eg-scale, 1));
        border-radius: 50%;
        background: var(--eg-primary);
        color: var(--eg-on-fill);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        touch-action: none;
        z-index: 2;
        --eg-icon-size: calc(28px * var(--eg-scale, 1));
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
        min-height: calc(64px * var(--eg-scale, 1));
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
        padding: 0 calc(16px * var(--eg-scale, 1));
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
        gap: calc(8px * var(--eg-scale, 1));
        font-size: calc(17px * var(--eg-scale, 1));
        font-weight: 600;
        --eg-icon-size: calc(24px * var(--eg-scale, 1));
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
        font-size: calc(12px * var(--eg-scale, 1));
        color: var(--eg-text-3);
        text-align: center;
      }
      .caption.st-opened {
        color: var(--eg-success);
      }
      .caption.st-error {
        color: var(--eg-error);
      }
      /* спиннер на ключе слайдера / иконке пилюли во время открытия */
      .knob.loading eg-icon,
      .pill.st-opening .content eg-icon {
        animation: eg-spin 0.8s linear infinite;
      }
      @keyframes eg-spin {
        to {
          transform: rotate(360deg);
        }
      }
      @keyframes eg-pulse {
        0%,
        100% {
          opacity: 0.12;
        }
        50% {
          opacity: 0.26;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .fill,
        .knob {
          transition: none;
        }
        .knob.loading eg-icon,
        .pill.st-opening .content eg-icon,
        .track.st-opening .fill {
          animation: none;
        }
      }
    `],p([u()],$.prototype,"mode",2),p([u({type:Boolean})],$.prototype,"disabled",2),p([u()],$.prototype,"label",2),p([u()],$.prototype,"status",2),p([f()],$.prototype,"_progress",2),p([f()],$.prototype,"_arming",2),$=p([A("eg-open-control")],$);function qe(s,t,e=!1){return!t||s==="denied"?!1:s==="granted"||e}function Ve(s,t,e){return s?t==="denied"?"denied":t==="prompt"&&!e?"prompt":"none":"no_https"}var G=class G{constructor(t,e=()=>{}){this._getConn=t;this._onChange=e;this.active=!1;this.lastError=""}hasGrantedBefore(){try{return typeof localStorage<"u"&&localStorage.getItem(G._GRANT_KEY)==="1"}catch{return!1}}markGranted(){try{typeof localStorage<"u"&&localStorage.setItem(G._GRANT_KEY,"1")}catch{}}async queryPermission(){try{return(await navigator.permissions?.query({name:"microphone"}))?.state??"unknown"}catch{return"unknown"}}get secure(){return typeof window<"u"&&window.isSecureContext===!0}async start(){if(this.active)return;let t=this._getConn();if(!t){this._fail("\u043D\u0435\u0442 \u0441\u0432\u044F\u0437\u0438 \u0441 Home Assistant");return}if(!navigator.mediaDevices?.getUserMedia){this._fail("\u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D (\u043D\u0443\u0436\u0435\u043D HTTPS-origin)");return}try{let e=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0}}),i=window.AudioContext||window.webkitAudioContext,r=new i,a=r.sampleRate,n=this._sub;(!n||n.sampleRate!==a)&&(n={handlerId:(await t.sendMessagePromise({type:"elektronny_gorod/intercom_uplink",sample_rate:a})).handler_id,sampleRate:a},this._sub=n);let d=n.handlerId,l=t.socket;await r.audioWorklet.addModule(this._workletUrl());let g=new AudioWorkletNode(r,"eg-pcm-int16",{numberOfOutputs:0});g.port.onmessage=h=>{let x=h.data,y=new Uint8Array(1+x.byteLength);y[0]=d,y.set(new Uint8Array(x.buffer),1),l.readyState===1&&l.send(y)};let m=r.createMediaStreamSource(e);m.connect(g),this._ctx={ac:r,stream:e,node:g,src:m},this.active=!0,this.lastError="",this.markGranted(),this._onChange()}catch(e){this._fail(e instanceof Error?e.message:String(e))}}stop(){let t=this._ctx;if(t){try{t.node.port.onmessage=null,t.node.disconnect(),t.src.disconnect()}catch{}try{t.stream.getTracks().forEach(e=>e.stop())}catch{}try{t.ac.close()}catch{}}if(this._ctx=void 0,this.active=!1,this._wUrl){try{URL.revokeObjectURL(this._wUrl)}catch{}this._wUrl=void 0}this._onChange()}_fail(t){this.lastError=t,this.stop()}_workletUrl(){if(this._wUrl)return this._wUrl;let t=`
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
      registerProcessor("eg-pcm-int16", EgPcmInt16);`;return this._wUrl=URL.createObjectURL(new Blob([t],{type:"application/javascript"})),this._wUrl}};G._GRANT_KEY="eg-intercom-mic-granted";var re=G;var _t=new Set(["slide","hold","tap"]);function Ie(s,t){return s&&_t.has(s)?s:t?"slide":"hold"}function We(){return typeof window<"u"&&typeof window.matchMedia=="function"&&window.matchMedia("(pointer: coarse)").matches}var bt={ringing:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432",connecting:"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026",active:"\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440",ended:"\u0412\u044B\u0437\u043E\u0432 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D",error:"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430"},se=new Set(["ringing","connecting","active","error"]),xt=6e3,yt=3e3,Ke=3e4,wt=2500,v=class extends _{constructor(){super(...arguments);this._config={};this._muted=!1;this._audioBlocked=!1;this._micActive=!1;this._micPerm="unknown";this._openStatus="idle";this._now=Date.now();this._ringingSince=0;this._errDismissed=new Set;this._endedEntity="";this._endedDuration="";this._doorbells=[];this._openAction="hold";this._prevKey="";this._prevPhases=new Map;this._mic=new re(()=>this.hass?.connection,()=>{this._micActive=this._mic.active,this.requestUpdate()});this._clearEnded=()=>{this._endedHide&&(clearTimeout(this._endedHide),this._endedHide=void 0),this._endedEntity="",this.requestUpdate()};this._unmute=()=>{this._muted=!1,this._audioBlocked=!1};this._answer=()=>{this.hass?.callService("elektronny_gorod","answer")};this._hangup=()=>{this.hass?.callService("elektronny_gorod","hangup")};this._toggleMute=()=>{this._muted=!this._muted};this._toggleMic=async()=>{this._mic.active?this._mic.stop():await this._mic.start(),this._micPerm=await this._mic.queryPermission()};this._open=async()=>{let e=this._active?.lock;if(!(!e||!this.hass)){this._openStatus="opening";try{await this.hass.callService("lock","unlock",{entity_id:e}),this._openStatus="opened"}catch{this._openStatus="error"}this._openReset&&clearTimeout(this._openReset),this._openReset=window.setTimeout(()=>{this._openStatus="idle",this.requestUpdate()},yt)}};this._dismiss=()=>{this.dispatchEvent(new CustomEvent("eg-dismiss",{bubbles:!0,composed:!0}))};this._retry=()=>{this.hass?.callService("elektronny_gorod","answer")}}setConfig(e){let i=e?.doorbells??(e?.call_state?[{call_state:e.call_state,doorbell_camera:e.doorbell_camera,lock:e.lock,name:e.name,address:e.address}]:[]);if(!i.length||i.some(r=>!r.call_state))throw new Error("eg-intercom-call-card: \u0443\u043A\u0430\u0436\u0438\u0442\u0435 'doorbells' (\u0441 call_state) \u0438\u043B\u0438 'call_state'");this._config=e,this._doorbells=i,this._openAction=Ie(e.open_action,We())}getCardSize(){return 8}static getStubConfig(){return{camera:"",doorbells:[{call_state:"",doorbell_camera:"",lock:""}]}}disconnectedCallback(){super.disconnectedCallback(),this._mic.stop(),this._stopTick(),this._errHide&&clearTimeout(this._errHide),this._openReset&&clearTimeout(this._openReset),this._endedHide&&clearTimeout(this._endedHide)}_phaseOf(e){let i=this.hass?.states[e.call_state]?.state;return Oe(i)}get _active(){let e=this._doorbells.find(i=>se.has(this._phaseOf(i))&&!this._errDismissed.has(i.call_state));if(e)return e;if(this._endedEntity)return this._doorbells.find(i=>i.call_state===this._endedEntity)}get _phase(){let e=this._active;if(!e)return"idle";let i=this._phaseOf(e);return se.has(i)?i:e.call_state===this._endedEntity?"ended":"idle"}get _intercomName(){let e=this._active;if(e?.name)return e.name;let r=(e?this.hass?.states[e.call_state]?.attributes:void 0)?.intercom_name;return(typeof r=="string"?r.replace(/\s+/g," ").trim():"")||this._config.name||"\u0414\u043E\u043C\u043E\u0444\u043E\u043D"}get _address(){return this._active?.address??this._config.address??""}get _startedAtMs(){let e=this._active,i=e?this.hass?.states[e.call_state]?.attributes?.started_at:void 0;if(typeof i!="string")return;let r=Date.parse(i);return Number.isNaN(r)?void 0:r}willUpdate(e){if(!e.has("hass"))return;for(let a of this._doorbells){let n=this._phaseOf(a),d=this._prevPhases.get(a.call_state);this._prevPhases.set(a.call_state,n),this._errDismissed.has(a.call_state)&&n!=="error"&&this._errDismissed.delete(a.call_state),n==="ended"&&d!==void 0&&se.has(d)&&d!=="error"&&this._enterEnded(a),this._endedEntity===a.call_state&&se.has(n)&&this._clearEnded()}let i=this._active,r=i?`${i.call_state}|${this._phase}`:"idle";r!==this._prevKey&&(this._onPhase(this._phase,i),this._prevKey=r)}_enterEnded(e){this._endedDuration=this._durationOf(e),this._endedEntity=e.call_state,this._endedHide&&clearTimeout(this._endedHide),this._endedHide=window.setTimeout(()=>this._clearEnded(),wt)}_durationOf(e){let i=this.hass?.states[e.call_state]?.attributes?.started_at;if(typeof i!="string")return"";let r=Date.parse(i);return Number.isNaN(r)?"":this._mmss(Math.max(0,Math.floor((Date.now()-r)/1e3)))}_onPhase(e,i){e==="active"?this._enterActive():e==="ringing"?(this._ringingSince=Date.now(),this._startTick()):this._exitActive(),e==="error"&&i&&this._scheduleErrDismiss(i.call_state),(e==="idle"||e==="ringing")&&(this._openStatus="idle")}async _enterActive(){if(this._muted=!1,this._audioBlocked=this._detectAudioBlocked(),this._startTick(),this._config.mic===!1||(this._micPerm=await this._mic.queryPermission(),this._phase!=="active"))return;this._config.mic_autostart!==!1&&qe(this._micPerm,this._mic.secure,this._mic.hasGrantedBefore())&&(await this._mic.start(),this._micPerm=await this._mic.queryPermission())}_detectAudioBlocked(){let e=navigator.userActivation;return e?!e.hasBeenActive:!1}_exitActive(){this._mic.stop(),this._stopTick(),this._audioBlocked=!1}_startTick(){this._stopTick(),this._now=Date.now(),this._tick=window.setInterval(()=>{this._now=Date.now()},1e3)}_stopTick(){this._tick&&(clearInterval(this._tick),this._tick=void 0)}_scheduleErrDismiss(e){this._errHide&&clearTimeout(this._errHide),this._errHide=window.setTimeout(()=>{this._errDismissed=new Set(this._errDismissed).add(e),this.requestUpdate()},xt)}_timerText(){let e=this._startedAtMs;if(e===void 0)return"";let i=Math.max(0,Math.floor((this._now-e)/1e3));return this._mmss(i)}_mmss(e){let i=String(Math.floor(e/60)).padStart(2,"0"),r=String(e%60).padStart(2,"0");return`${i}:${r}`}_answerWindow(){if(!this._ringingSince)return{text:"",fraction:0};let e=Math.max(0,Ke-(this._now-this._ringingSince)),i=Math.ceil(e/1e3);return{text:`${Math.floor(i/60)}:${String(i%60).padStart(2,"0")}`,fraction:e/Ke}}_stageState(e,i,r){if(r==="ended")return"ended";if(e.isError)return"connection_lost";let a=i?this.hass?.states[i]:void 0;return!a||a.state==="unavailable"?"camera_off":"live"}get _micBanner(){return this._config.mic===!1||this._phase!=="active"||this._micActive?"none":Ve(this._mic.secure,this._micPerm,this._mic.hasGrantedBefore())}get _micBlocked(){return!this._mic.secure||this._micPerm==="denied"}render(){let e=this._active;if(!e)return this._renderIdle();let i=this._phase,r=Ne(i),a=Be(r.video,{camera:this._config.camera,doorbell_camera:e.doorbell_camera});if(this._config.layout==="compact")return this._renderCompact(e,i,r,a);let n=this._stageState(r,a,i);return o`
      <ha-card class="phase-${i}">
        <div class="content">
          ${this._renderHeader()}
          ${this._renderStatus(r,i)}
          <div class="stage">
            <eg-call-stage
              .hass=${this.hass}
              .entity=${a}
              .muted=${this._muted||this._audioBlocked}
              .live=${n==="live"}
              .soundOff=${i==="active"&&this._muted&&!this._audioBlocked}
              .stageState=${n}
              .audioBlocked=${this._audioBlocked}
              @unmute=${this._unmute}
            ></eg-call-stage>
          </div>
          <div class="controls">
            ${(()=>{let d=this._micBanner;return d!=="none"?this._renderMicBanner(d):c})()}
            <div class="open-area">
              ${r.showOpen?this._renderOpen():c}
            </div>
            ${this._renderActions(r)}
          </div>
        </div>
      </ha-card>
    `}_renderHeader(){let e=this._address;return o`
      <header>
        <div class="hgroup">
          <span class="name" title=${this._intercomName}>${this._intercomName}</span>
          ${e?o`<span class="addr">${e}</span>`:c}
        </div>
        <button class="close" @click=${this._dismiss} aria-label="Свернуть">
          <eg-icon name="x"></eg-icon>
        </button>
      </header>
    `}_renderStatus(e,i){let r=e.showTimer&&this._config.timer!=="off",a=e.showAnswerWindow?this._answerWindow():null;return o`
      <div class="statusrow">
        <div class="strow">
          <span class="badge" style="--badge:${ve(i)}">
            <span class="dot" aria-hidden="true"></span>
            <span>${bt[i]??""}</span>
          </span>
          ${a?o`<span class="countdown"><eg-icon name="timer"></eg-icon>${a.text}</span>`:r?o`<span class="timer">${this._timerText()}</span>`:i==="ended"&&this._endedDuration?o`<span class="timer ended-dur">${this._endedDuration}</span>`:c}
        </div>
        ${a?o`<div class="window"><div class="fill" style="width:${a.fraction*100}%"></div></div>`:c}
      </div>
    `}_doorbellNames(){return this._doorbells.map(e=>{let i=this.hass?.states[e.call_state]?.attributes?.intercom_name;return e.name??(typeof i=="string"?i:"")}).filter(Boolean)}_renderIdle(){let e=this._doorbellNames();return o`
      <ha-card class="idle">
        <div class="idle-box" role="status">
          <div class="idle-ico"><eg-icon name="door-closed"></eg-icon></div>
          <div class="idle-title">${this._config.idle_text??"\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u044B\u0437\u043E\u0432\u0430"}</div>
          <div class="idle-sub">Видео появится при звонке в домофон</div>
          ${e.length?o`<div class="idle-chips">
                ${e.map(i=>o`<span class="chip"><eg-icon name="door-open"></eg-icon>${i}</span>`)}
              </div>`:c}
        </div>
      </ha-card>
    `}_renderCompact(e,i,r,a){let n=this._stageState(r,a,i);return o`
      <ha-card class="compact phase-${i}">
        <div class="cx-thumb">
          ${a?o`<eg-call-video .hass=${this.hass} .entity=${a} .muted=${!0}></eg-call-video>`:c}
          ${n==="live"?o`<span class="cx-live">LIVE</span>`:c}
        </div>
        <div class="cx-info">
          <span class="cx-name" title=${this._intercomName}>${this._intercomName}</span>
          <span class="cx-status" style="--badge:${ve(i)}">
            <span class="cx-dot" aria-hidden="true"></span>
            <span>${this._compactStatus(i)}</span>
          </span>
        </div>
        <div class="cx-btns">
          ${r.showOpen&&e.lock?this._quickBtn("key-round","\u041E\u0442\u043A\u0440\u044B\u0442\u044C",this._open,"q-open"):c}
          ${r.actions.map(d=>this._quickAction(d))}
        </div>
      </ha-card>
    `}_quickAction(e){switch(e){case"accept":return this._quickBtn("phone","\u041F\u0440\u0438\u043D\u044F\u0442\u044C",this._answer,"q-accept");case"reject":case"cancel":case"hangup":return this._quickBtn("phone-off","\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C",this._hangup,"q-reject");case"close":return this._quickBtn("x","\u0417\u0430\u043A\u0440\u044B\u0442\u044C",this._clearEnded,"");default:return c}}_quickBtn(e,i,r,a){return o`
      <button class="q-btn ${a}" @click=${r} aria-label=${i}>
        <eg-icon name=${e}></eg-icon>
      </button>
    `}_compactStatus(e){return e==="ringing"?`\u0412\u044B\u0437\u043E\u0432 \xB7 ${this._answerWindow().text}`:e==="active"?`\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440 \xB7 ${this._timerText()}`:e==="connecting"?"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026":e==="ended"?this._endedDuration?`\u0417\u0430\u0432\u0435\u0440\u0448\u0451\u043D \xB7 ${this._endedDuration}`:"\u0417\u0430\u0432\u0435\u0440\u0448\u0451\u043D":e==="error"?"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430":""}_renderMicBanner(e){let r={no_https:{title:"\u041C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D",sub:"\u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 Home Assistant \u043F\u043E HTTPS, \u0447\u0442\u043E\u0431\u044B \u0433\u043E\u0432\u043E\u0440\u0438\u0442\u044C \u0432 \u0434\u043E\u043C\u043E\u0444\u043E\u043D."},denied:{title:"\u0414\u043E\u0441\u0442\u0443\u043F \u043A \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D\u0443 \u0437\u0430\u043F\u0440\u0435\u0449\u0451\u043D",sub:"\u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u0435 \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u0434\u043B\u044F \u044D\u0442\u043E\u0433\u043E \u0441\u0430\u0439\u0442\u0430 \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0430.",cta:"\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C"},prompt:{title:"\u041D\u0443\u0436\u0435\u043D \u0434\u043E\u0441\u0442\u0443\u043F \u043A \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D\u0443",sub:"\u041D\u0430\u0436\u043C\u0438\u0442\u0435 \xAB\u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u044C\xBB, \u0447\u0442\u043E\u0431\u044B \u0432\u0430\u0441 \u0431\u044B\u043B\u043E \u0441\u043B\u044B\u0448\u043D\u043E.",cta:"\u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u044C"}}[e];return o`
      <div class="mic-banner" role="alert">
        <eg-icon name="mic-off"></eg-icon>
        <div class="mb-text">
          <span class="mb-title">${r.title}</span>
          <span class="mb-sub">${r.sub}</span>
        </div>
        ${r.cta?o`<button class="mb-btn" @click=${this._toggleMic}>${r.cta}</button>`:c}
      </div>
    `}_renderOpen(){return o`
      <eg-open-control
        .mode=${this._openAction}
        .status=${this._openStatus}
        ?disabled=${!this._active?.lock}
        @open=${this._open}
      ></eg-open-control>
    `}_circle(e,i,r,a=""){return o`
      <button class="circle ${a}" @click=${r} aria-label=${i}>
        <span class="ic"><eg-icon name=${e}></eg-icon></span>
        <small>${i}</small>
      </button>
    `}_renderActions(e){return o`<div class="actions">${e.actions.map(i=>this._renderAction(i))}</div>`}_renderAction(e){switch(e){case"accept":return this._circle("phone","\u041F\u0440\u0438\u043D\u044F\u0442\u044C",this._answer,"accept");case"reject":return this._circle("phone-off","\u041E\u0442\u043A\u043B\u043E\u043D\u0438\u0442\u044C",this._hangup,"reject");case"cancel":return this._circle("phone-off","\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C",this._hangup,"reject");case"connecting":return this._spinnerBtn("\u0421\u043E\u0435\u0434\u0438\u043D\u044F\u0435\u043C\u2026");case"mic":return this._config.mic===!1?c:this._renderMic();case"sound":return this._audioBlocked?this._circle("volume-x","\u0417\u0432\u0443\u043A \u0432\u044B\u043A\u043B.",this._unmute,"warn"):this._circle(this._muted?"volume-x":"volume-2","\u0417\u0432\u0443\u043A",this._toggleMute);case"hangup":return this._circle("phone-off","\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C",this._hangup,"reject");case"retry":return this._circle("refresh-cw","\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",this._retry,"retry");case"close":return this._circle("x","\u0417\u0430\u043A\u0440\u044B\u0442\u044C",this._clearEnded);default:return c}}_spinnerBtn(e){return o`
      <div class="circle spinner-btn" role="status" aria-label=${e} aria-busy="true">
        <span class="ic"><eg-icon class="spin" name="loader-circle"></eg-icon></span>
        <small>${e}</small>
      </div>
    `}_renderMic(){if(this._micBlocked)return this._circle("mic-off","\u041D\u0435\u0442 \u0434\u043E\u0441\u0442\u0443\u043F\u0430",this._toggleMic,"mic-blocked");let e=this._micActive?"mic":"mic-off",i=this._micActive?"\u0412\u044B\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D":"\u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D";return o`<button class="circle" @click=${this._toggleMic} aria-label=${i}>
      <span class="ic"><eg-icon name=${e}></eg-icon></span><small>Микрофон</small>
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
        /* заполняем высоту карточки; вертикальный экран → верт. отступы вдвое больше
           горизонтальных (16), с учётом safe-area панели/телефона */
        min-height: 100%;
        padding: max(32px, env(safe-area-inset-top)) 16px max(32px, env(safe-area-inset-bottom));
        box-sizing: border-box;
      }
      /* Адаптивный масштаб контента: телефон = 1, на большом экране крупнее
         (настенная панель/десктоп — «читаемо с ~1м», UX §10). Наследуется в
         дочерние компоненты (open-control) через --eg-scale. */
      .content,
      ha-card.idle {
        --eg-scale: 1;
      }
      @container (min-width: 700px) {
        .content,
        ha-card.idle {
          --eg-scale: 1.35;
        }
      }
      @container (min-width: 1100px) {
        .content,
        ha-card.idle {
          --eg-scale: 1.7;
        }
      }
      @container (min-width: 1600px) {
        .content,
        ha-card.idle {
          --eg-scale: 2;
        }
      }
      /* шапка/статус/видео — сверху, фиксированной высоты */
      header,
      .statusrow,
      .stage {
        flex: none;
      }
      /* зона контролов заполняет остаток: слайдер по центру, кнопки — по нижней кромке */
      .controls {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .controls .open-area {
        flex: 1;
        align-items: center;
      }
      .controls .actions {
        margin-top: auto;
      }
      /* ---- широкий контейнер (планшет / настенная панель / десктоп): 2 колонки.
         Порог 760px: видео + контролы РЯДОМ вертикально компактнее вертикального
         стека, поэтому на невысоких экранах ничего не переполняется (у стека
         video 16:9 + баннер + слайдер + кнопки не влезают по высоте). */
      @container (min-width: 760px) {
        .content {
          display: grid;
          /* Узкая колонка контролов фикс. ширины → видео (1fr) получает
             максимум ширины, а значит и высоты (оно всегда 16:9). Кнопки/
             слайдер — базового размера (.controls сбрасывает --eg-scale в 1):
             на десктопе (мышь, близко) укрупнённые touch-таргеты не нужны. */
          grid-template-columns: 1fr 320px;
          grid-template-areas:
            "header header"
            "status status"
            "stage controls";
          column-gap: 28px;
          row-gap: 20px;
          align-items: start;
          /* grid default align-content = stretch → строки растягивались (дыры);
             start = контент сверху, строка stage/controls по высоте видео */
          align-content: start;
          padding: 24px;
        }
        header {
          grid-area: header;
        }
        .statusrow {
          grid-area: status;
        }
        .stage {
          grid-area: stage;
          align-self: start;
        }
        /* Колонка контролов = высоте видео (align-self: stretch). Flex-поток
           (из базового .controls): баннер сверху, слайдер по центру свободного
           места, кнопки по нижней кромке — без наложения при любой высоте видео
           (в т.ч. на узком 760–900, где видео невысокое). */
        .controls {
          grid-area: controls;
          align-self: stretch;
          /* Базовый размер контролов на широком экране: --eg-scale укрупняет
             текст/оверлеи для читаемости, но кнопки/слайдер от него раздувались
             до ~2× («как для слепых» на десктопе). Здесь сбрасываем в 1. */
          --eg-scale: 1;
        }
      }
      /* ≥900px: видео уже выше стека контролов → абсолютное позиционирование,
         слайдер строго по ЦЕНТРУ видео, кнопки по нижней кромке, баннер сверху.
         На 760–900 остаётся flex-поток (выше) — иначе слайдер/кнопки налезали
         бы друг на друга на невысоком видео. */
      @container (min-width: 900px) {
        .controls {
          position: relative;
          display: block;
        }
        .controls .mic-banner {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
        }
        .controls .open-area {
          position: absolute;
          top: 50%;
          left: 0;
          right: 0;
          transform: translateY(-50%);
        }
        .controls .actions {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
        }
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
        font-size: calc(22px * var(--eg-scale, 1));
        font-weight: 700;
        line-height: 1.15;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .addr {
        font-size: calc(13px * var(--eg-scale, 1));
        color: var(--eg-text-2);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .close {
        flex: none;
        width: calc(44px * var(--eg-scale, 1));
        height: calc(44px * var(--eg-scale, 1));
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
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
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
        gap: calc(7px * var(--eg-scale, 1));
        padding: calc(5px * var(--eg-scale, 1)) calc(12px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 600;
        color: var(--badge, var(--eg-text-2));
        background: color-mix(in srgb, var(--badge, var(--eg-text-2)) 18%, transparent);
      }
      .badge .dot {
        width: calc(8px * var(--eg-scale, 1));
        height: calc(8px * var(--eg-scale, 1));
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
      }
      .countdown {
        display: inline-flex;
        align-items: center;
        gap: calc(6px * var(--eg-scale, 1));
        font-size: calc(15px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
      .countdown eg-icon {
        --eg-icon-size: calc(15px * var(--eg-scale, 1));
      }
      .timer {
        font-family: var(--eg-mono);
        font-size: calc(17px * var(--eg-scale, 1));
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
        gap: calc(12px * var(--eg-scale, 1));
        padding: calc(12px * var(--eg-scale, 1));
        border-radius: var(--eg-r-md);
        background: var(--eg-warning-bg);
      }
      .mic-banner > eg-icon {
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
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
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 600;
        color: var(--eg-warning);
      }
      .mb-sub {
        font-size: calc(12px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
      .mb-btn {
        flex: none;
        border: 1px solid var(--eg-warning);
        background: transparent;
        color: var(--eg-warning);
        font: inherit;
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 600;
        border-radius: var(--eg-r-full);
        padding: calc(6px * var(--eg-scale, 1)) calc(14px * var(--eg-scale, 1));
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
        gap: calc(28px * var(--eg-scale, 1));
        justify-content: center;
        align-items: flex-start;
        flex-wrap: wrap;
      }
      .circle {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: calc(8px * var(--eg-scale, 1));
        border: none;
        background: none;
        cursor: pointer;
        color: var(--eg-text);
        font: inherit;
        padding: 0;
      }
      .circle .ic {
        width: calc(68px * var(--eg-scale, 1));
        height: calc(68px * var(--eg-scale, 1));
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .circle .ic eg-icon {
        --eg-icon-size: calc(28px * var(--eg-scale, 1));
      }
      .circle small {
        font-size: calc(12px * var(--eg-scale, 1));
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
      /* ---- idle-заглушка (узел aSs3Z) ---- */
      ha-card.idle {
        height: 100%;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 18px;
      }
      .idle-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: calc(18px * var(--eg-scale, 1));
        text-align: center;
      }
      .idle-ico {
        width: calc(76px * var(--eg-scale, 1));
        height: calc(76px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .idle-ico eg-icon {
        --eg-icon-size: calc(36px * var(--eg-scale, 1));
        color: var(--eg-text-3);
      }
      .idle-title {
        font-size: calc(22px * var(--eg-scale, 1));
        font-weight: 700;
        color: var(--eg-text);
      }
      .idle-sub {
        font-size: calc(15px * var(--eg-scale, 1));
        color: var(--eg-text-2);
        max-width: 40ch;
      }
      .idle-chips {
        display: flex;
        flex-wrap: wrap;
        gap: calc(10px * var(--eg-scale, 1));
        justify-content: center;
        padding-top: calc(6px * var(--eg-scale, 1));
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: calc(7px * var(--eg-scale, 1));
        padding: calc(9px * var(--eg-scale, 1)) calc(16px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        color: var(--eg-text-2);
        font-size: calc(14px * var(--eg-scale, 1));
        font-weight: 500;
      }
      .chip eg-icon {
        --eg-icon-size: calc(16px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
      /* ---- компактная строка (layout: compact) — узел aSs3Z ---- */
      ha-card.compact {
        height: auto;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        box-sizing: border-box;
      }
      .cx-thumb {
        position: relative;
        width: 80px;
        height: 60px;
        flex: none;
        border-radius: 10px;
        overflow: hidden;
        background: #20262b;
      }
      .cx-thumb eg-call-video {
        position: absolute;
        inset: 0;
      }
      .cx-live {
        position: absolute;
        top: 6px;
        left: 6px;
        padding: 2px 6px;
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 0.04em;
      }
      .cx-info {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .cx-name {
        font-size: 15px;
        font-weight: 700;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .cx-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 500;
        color: var(--badge, var(--eg-text-2));
      }
      .cx-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
        flex: none;
      }
      .cx-btns {
        display: flex;
        gap: 8px;
        flex: none;
      }
      .q-btn {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .q-btn eg-icon {
        --eg-icon-size: 20px;
      }
      .q-btn.q-open {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      .q-btn.q-accept {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .q-btn.q-reject {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
    `],p([u({attribute:!1})],v.prototype,"hass",2),p([f()],v.prototype,"_config",2),p([f()],v.prototype,"_muted",2),p([f()],v.prototype,"_audioBlocked",2),p([f()],v.prototype,"_micActive",2),p([f()],v.prototype,"_micPerm",2),p([f()],v.prototype,"_openStatus",2),p([f()],v.prototype,"_now",2),p([f()],v.prototype,"_ringingSince",2),p([f()],v.prototype,"_errDismissed",2),p([f()],v.prototype,"_endedEntity",2),p([f()],v.prototype,"_endedDuration",2),v=p([A("eg-intercom-call-card")],v);window.customCards=window.customCards||[];window.customCards.push({type:"eg-intercom-call-card",name:"\u042D\u0413 \u0414\u043E\u043C\u043E\u0444\u043E\u043D \u2014 \u042D\u043A\u0440\u0430\u043D \u0432\u044B\u0437\u043E\u0432\u0430",description:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432 \u0438 \u0440\u0430\u0437\u0433\u043E\u0432\u043E\u0440 \u0441 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u043E\u043C: \u0432\u0438\u0434\u0435\u043E+\u0437\u0432\u0443\u043A, \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C, \u043F\u0440\u0438\u043D\u044F\u0442\u044C/\u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C, \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D. \u041E\u0434\u043D\u0430 \u043A\u0430\u0440\u0442\u0430 \u043D\u0430 \u0432\u0441\u0435 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u044B.",preview:!1});export{v as EgIntercomCallCard};
