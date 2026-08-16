import {HttpInterceptorFn} from '@angular/common/http';
import {environment} from '../../../environments/environment';

export const apiPrefixInterceptor: HttpInterceptorFn = (req, next) =>
    next(req.clone({url: `${environment.apiUrl}${req.url}`}));
